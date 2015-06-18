#-------------------------------------------------------------------------
# Copyright (c) Microsoft.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#--------------------------------------------------------------------------
import ast
import json
import sys

from datetime import datetime
from azure.common import (
    WindowsAzureError,
)
from .models import (
    Queue,
    Topic,
    Subscription,
    Rule,
    EventHub,
    AuthorizationRule,
    Message,
)
from ._internal import (
    WindowsAzureData,
    _general_error_handler,
    _lower,
    _str,
    _ERROR_MESSAGE_NOT_PEEK_LOCKED_ON_DELETE,
    _ERROR_MESSAGE_NOT_PEEK_LOCKED_ON_UNLOCK,
    _ERROR_EVENT_HUB_NOT_FOUND,
    _ERROR_QUEUE_NOT_FOUND,
    _ERROR_TOPIC_NOT_FOUND,
    _XmlWriter,
    _make_etree_ns_attr_name,
    _get_etree_text,
    ETree,
    _ETreeXmlToObject,
)
from ._http import HTTPError


class _XmlSchemas:
    SchemaInstance = 'http://www.w3.org/2001/XMLSchema-instance'
    SerializationArrays = 'http://schemas.microsoft.com/2003/10/Serialization/Arrays'
    ServiceBus = 'http://schemas.microsoft.com/netservices/2010/10/servicebus/connect'
    DataServices = 'http://schemas.microsoft.com/ado/2007/08/dataservices'
    DataServicesMetadata = 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'
    Atom = 'http://www.w3.org/2005/Atom'


def _create_message(response, service_instance):
    ''' Create message from response.

    response:
        response from service bus cloud server.
    service_instance:
        the service bus client.
    '''
    respbody = response.body
    custom_properties = {}
    broker_properties = None
    message_type = None
    message_location = None

    # gets all information from respheaders.
    for name, value in response.headers:
        if name.lower() == 'brokerproperties':
            broker_properties = json.loads(value)
        elif name.lower() == 'content-type':
            message_type = value
        elif name.lower() == 'location':
            message_location = value
        elif name.lower() not in ['content-type',
                                  'brokerproperties',
                                  'transfer-encoding',
                                  'server',
                                  'location',
                                  'date']:
            if '"' in value:
                value = value[1:-1]
                try:
                    custom_properties[name] = datetime.strptime(
                        value, '%a, %d %b %Y %H:%M:%S GMT')
                except ValueError:
                    custom_properties[name] = value
            else:  # only int, float or boolean
                if value.lower() == 'true':
                    custom_properties[name] = True
                elif value.lower() == 'false':
                    custom_properties[name] = False
                # int('3.1') doesn't work so need to get float('3.14') first
                elif str(int(float(value))) == value:
                    custom_properties[name] = int(value)
                else:
                    custom_properties[name] = float(value)

    if message_type == None:
        message = Message(
            respbody, service_instance, message_location, custom_properties,
            'application/atom+xml;type=entry;charset=utf-8', broker_properties)
    else:
        message = Message(respbody, service_instance, message_location,
                          custom_properties, message_type, broker_properties)
    return message

# convert functions

_etree_sb_feed_namespaces = {
    'atom': _XmlSchemas.Atom,
    'i': _XmlSchemas.SchemaInstance,
    'sb': _XmlSchemas.ServiceBus,
    'arrays': _XmlSchemas.SerializationArrays,
}


def _convert_response_to_rule(response):
    root = ETree.fromstring(response.body)
    return _convert_etree_element_to_rule(root)


def _convert_etree_element_to_rule(entry_element):
    ''' Converts entry element to rule object.

    The format of xml for rule:
<entry xmlns='http://www.w3.org/2005/Atom'>
<content type='application/xml'>
<RuleDescription
    xmlns:i="http://www.w3.org/2001/XMLSchema-instance"
    xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
    <Filter i:type="SqlFilterExpression">
        <SqlExpression>MyProperty='XYZ'</SqlExpression>
    </Filter>
    <Action i:type="SqlFilterAction">
        <SqlExpression>set MyProperty2 = 'ABC'</SqlExpression>
    </Action>
</RuleDescription>
</content>
</entry>
    '''
    rule = Rule()

    rule_element = entry_element.find('./atom:content/sb:RuleDescription', _etree_sb_feed_namespaces)
    if rule_element is not None:
        filter_element = rule_element.find('./sb:Filter', _etree_sb_feed_namespaces)
        if filter_element is not None:
            rule.filter_type = filter_element.attrib.get(
                _make_etree_ns_attr_name(_etree_sb_feed_namespaces['i'], 'type'), None)
            sql_exp_element = filter_element.find('./sb:SqlExpression', _etree_sb_feed_namespaces)
            if sql_exp_element is not None:
                rule.filter_expression = sql_exp_element.text

        action_element = rule_element.find('./sb:Action', _etree_sb_feed_namespaces)
        if action_element is not None:
            rule.action_type = action_element.attrib.get(
                _make_etree_ns_attr_name(_etree_sb_feed_namespaces['i'], 'type'), None)
            sql_exp_element = action_element.find('./sb:SqlExpression', _etree_sb_feed_namespaces)
            if sql_exp_element is not None:
                rule.action_expression = sql_exp_element.text


    # extract id, updated and name value from feed entry and set them of rule.
    for name, value in _ETreeXmlToObject.get_entry_properties_from_element(
        entry_element, True, '/rules').items():
        setattr(rule, name, value)

    return rule


def _convert_response_to_queue(response):
    root = ETree.fromstring(response.body)
    return _convert_etree_element_to_queue(root)


def _convert_response_to_event_hub(response):
    root = ETree.fromstring(response.body)
    return _convert_etree_element_to_event_hub(root)


def _parse_bool(value):
    if value.lower() == 'true':
        return True
    return False


def _read_etree_element(parent_element, child_element_name, target_object, target_field_name, converter):
    child_element = parent_element.find('./sb:{0}'.format(child_element_name), _etree_sb_feed_namespaces)
    if child_element is not None:
        field_value = _get_etree_text(child_element)
        if converter is not None:
            field_value = converter(field_value)
        setattr(target_object, target_field_name, field_value)
        return True
    return False


def _convert_etree_element_to_queue(entry_element):
    ''' Converts entry element to queue object.

    The format of xml response for queue:
<QueueDescription
    xmlns=\"http://schemas.microsoft.com/netservices/2010/10/servicebus/connect\">
    <MaxSizeInBytes>10000</MaxSizeInBytes>
    <DefaultMessageTimeToLive>PT5M</DefaultMessageTimeToLive>
    <LockDuration>PT2M</LockDuration>
    <RequiresGroupedReceives>False</RequiresGroupedReceives>
    <SupportsDuplicateDetection>False</SupportsDuplicateDetection>
    ...
</QueueDescription>

    '''
    queue = Queue()

    # get node for each attribute in Queue class, if nothing found then the
    # response is not valid xml for Queue.
    invalid_queue = True

    queue_element = entry_element.find('./atom:content/sb:QueueDescription', _etree_sb_feed_namespaces)
    if queue_element is not None:
        mappings = [
            ('LockDuration', 'lock_duration', None),
            ('MaxSizeInMegabytes', 'max_size_in_megabytes', int),
            ('RequiresDuplicateDetection', 'requires_duplicate_detection', _parse_bool),
            ('RequiresSession', 'requires_session', _parse_bool),
            ('DefaultMessageTimeToLive', 'default_message_time_to_live', None),
            ('DeadLetteringOnMessageExpiration', 'dead_lettering_on_message_expiration', _parse_bool),
            ('DuplicateDetectionHistoryTimeWindow', 'duplicate_detection_history_time_window', None),
            ('EnableBatchedOperations', 'enable_batched_operations', _parse_bool),
            ('MaxDeliveryCount', 'max_delivery_count', int),
            ('MessageCount', 'message_count', int),
            ('SizeInBytes', 'size_in_bytes', int),
        ]

        for map in mappings:
            if _read_etree_element(queue_element, map[0], queue, map[1], map[2]):
                invalid_queue = False

    if invalid_queue:
        raise WindowsAzureError(_ERROR_QUEUE_NOT_FOUND)

    # extract id, updated and name value from feed entry and set them of queue.
    for name, value in _ETreeXmlToObject.get_entry_properties_from_element(
        entry_element, True).items():
        setattr(queue, name, value)

    return queue


def _convert_response_to_topic(response):
    root = ETree.fromstring(response.body)
    return _convert_etree_element_to_topic(root)


def _convert_etree_element_to_topic(entry_element):
    '''Converts entry element to topic

    The xml format for topic:
<entry xmlns='http://www.w3.org/2005/Atom'>
    <content type='application/xml'>
    <TopicDescription
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance"
        xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
        <DefaultMessageTimeToLive>P10675199DT2H48M5.4775807S</DefaultMessageTimeToLive>
        <MaxSizeInMegabytes>1024</MaxSizeInMegabytes>
        <RequiresDuplicateDetection>false</RequiresDuplicateDetection>
        <DuplicateDetectionHistoryTimeWindow>P7D</DuplicateDetectionHistoryTimeWindow>
        <DeadLetteringOnFilterEvaluationExceptions>true</DeadLetteringOnFilterEvaluationExceptions>
    </TopicDescription>
    </content>
</entry>
    '''
    topic = Topic()

    invalid_topic = True

    topic_element = entry_element.find('./atom:content/sb:TopicDescription', _etree_sb_feed_namespaces)
    if topic_element is not None:
        mappings = [
            ('DefaultMessageTimeToLive', 'default_message_time_to_live', None),
            ('MaxSizeInMegabytes', 'max_size_in_megabytes', int),
            ('RequiresDuplicateDetection', 'requires_duplicate_detection', _parse_bool),
            ('DuplicateDetectionHistoryTimeWindow', 'duplicate_detection_history_time_window', None),
            ('EnableBatchedOperations', 'enable_batched_operations', _parse_bool),
            ('SizeInBytes', 'size_in_bytes', int),
        ]

        for map in mappings:
            if _read_etree_element(topic_element, map[0], topic, map[1], map[2]):
                invalid_topic = False

    if invalid_topic:
        raise WindowsAzureError(_ERROR_TOPIC_NOT_FOUND)

    # extract id, updated and name value from feed entry and set them of topic.
    for name, value in _ETreeXmlToObject.get_entry_properties_from_element(
        entry_element, True).items():
        setattr(topic, name, value)

    return topic


def _convert_response_to_subscription(response):
    root = ETree.fromstring(response.body)
    return _convert_etree_element_to_subscription(root)


def _convert_etree_element_to_subscription(entry_element):
    '''Converts entry element to subscription

    The xml format for subscription:
<entry xmlns='http://www.w3.org/2005/Atom'>
    <content type='application/xml'>
    <SubscriptionDescription
        xmlns:i="http://www.w3.org/2001/XMLSchema-instance"
        xmlns="http://schemas.microsoft.com/netservices/2010/10/servicebus/connect">
        <LockDuration>PT5M</LockDuration>
        <RequiresSession>false</RequiresSession>
        <DefaultMessageTimeToLive>P10675199DT2H48M5.4775807S</DefaultMessageTimeToLive>
        <DeadLetteringOnMessageExpiration>false</DeadLetteringOnMessageExpiration>
        <DeadLetteringOnFilterEvaluationExceptions>true</DeadLetteringOnFilterEvaluationExceptions>
    </SubscriptionDescription>
    </content>
</entry>
    '''
    subscription = Subscription()

    subscription_element = entry_element.find('./atom:content/sb:SubscriptionDescription', _etree_sb_feed_namespaces)
    if subscription_element is not None:
        mappings = [
            ('LockDuration', 'lock_duration', None),
            ('RequiresSession', 'requires_session', _parse_bool),
            ('DefaultMessageTimeToLive', 'default_message_time_to_live', None),
            ('DeadLetteringOnFilterEvaluationExceptions', 'dead_lettering_on_filter_evaluation_exceptions', _parse_bool),
            ('DeadLetteringOnMessageExpiration', 'dead_lettering_on_message_expiration', _parse_bool),
            ('EnableBatchedOperations', 'enable_batched_operations', _parse_bool),
            ('MaxDeliveryCount', 'max_delivery_count', int),
            ('MessageCount', 'message_count', int),
        ]

        for map in mappings:
            _read_etree_element(subscription_element, map[0], subscription, map[1], map[2])

    for name, value in _ETreeXmlToObject.get_entry_properties_from_element(
        entry_element, True, '/subscriptions').items():
        setattr(subscription, name, value)

    return subscription


def _convert_etree_element_to_event_hub(entry_element):
    hub = EventHub()

    invalid_event_hub = True
    # get node for each attribute in EventHub class, if nothing found then the
    # response is not valid xml for EventHub.

    hub_element = entry_element.find('./atom:content/sb:EventHubDescription', _etree_sb_feed_namespaces)
    if hub_element is not None:
        mappings = [
            ('SizeInBytes', 'size_in_bytes', int),
            ('MessageRetentionInDays', 'message_retention_in_days', int),
            ('Status', 'status', None),
            ('UserMetadata', 'user_metadata', None),
            ('PartitionCount', 'partition_count', int),
            ('EntityAvailableStatus', 'entity_available_status', None),
        ]

        for map in mappings:
            if _read_etree_element(hub_element, map[0], hub, map[1], map[2]):
                invalid_event_hub = False

        ids = hub_element.find('./sb:PartitionIds', _etree_sb_feed_namespaces)
        if ids is not None:
            for id_node in ids.findall('./arrays:string', _etree_sb_feed_namespaces):
                value = _get_etree_text(id_node)
                if value:
                    hub.partition_ids.append(value)

        rules_nodes = hub_element.find('./sb:AuthorizationRules', _etree_sb_feed_namespaces)
        if rules_nodes is not None:
            invalid_event_hub = False
            for rule_node in rules_nodes.findall('./sb:AuthorizationRule', _etree_sb_feed_namespaces):
                rule = AuthorizationRule()

                mappings = [
                    ('ClaimType', 'claim_type', None),
                    ('ClaimValue', 'claim_value', None),
                    ('ModifiedTime', 'modified_time', None),
                    ('CreatedTime', 'created_time', None),
                    ('KeyName', 'key_name', None),
                    ('PrimaryKey', 'primary_key', None),
                    ('SecondaryKey', 'secondary_key', None),
                ]

                for map in mappings:
                    _read_etree_element(rule_node, map[0], rule, map[1], map[2])

                rights_nodes = rule_node.find('./sb:Rights', _etree_sb_feed_namespaces)
                if rights_nodes is not None:
                    for access_rights_node in rights_nodes.findall('./sb:AccessRights', _etree_sb_feed_namespaces):
                        node_value = _get_etree_text(access_rights_node)
                        if node_value:
                            rule.rights.append(node_value)

                hub.authorization_rules.append(rule)

    if invalid_event_hub:
        raise WindowsAzureError(_ERROR_EVENT_HUB_NOT_FOUND)

    # extract id, updated and name value from feed entry and set them of queue.
    for name, value in _ETreeXmlToObject.get_entry_properties_from_element(
        entry_element, True).items():
        if name == 'name':
            value = value.partition('?')[0]
        setattr(hub, name, value)

    return hub


def _convert_object_to_feed_entry(obj, rootName, content_writer):
    updated_str = datetime.utcnow().isoformat()
    if datetime.utcnow().utcoffset() is None:
        updated_str += '+00:00'

    writer = _XmlWriter()
    writer.preprocessor('<?xml version="1.0" encoding="utf-8" standalone="yes"?>')
    writer.start('entry', [
        ('xmlns:d', _XmlSchemas.DataServices, None),
        ('xmlns:m', _XmlSchemas.DataServicesMetadata, None),
        ('xmlns', _XmlSchemas.Atom, None),
        ])

    writer.element('title', '')
    writer.element('updated', updated_str)
    writer.start('author')
    writer.element('name', '')
    writer.end('author')
    writer.element('id', '')
    writer.start('content', [('type', 'application/xml', None)])
    writer.start(rootName, [
        ('xmlns:i', _XmlSchemas.SchemaInstance, None),
        ('xmlns', _XmlSchemas.ServiceBus, None),
        ])

    if obj:
        content_writer(writer, obj)

    writer.end(rootName)
    writer.end('content')
    writer.end('entry')

    xml = writer.xml()
    writer.close()

    return xml


def _convert_subscription_to_xml(sub):

    def _subscription_to_xml(writer, sub):
        writer.elements([
            ('LockDuration', sub.lock_duration, None),
            ('RequiresSession', sub.requires_session, _lower),
            ('DefaultMessageTimeToLive', sub.default_message_time_to_live, None),
            ('DeadLetteringOnMessageExpiration', sub.dead_lettering_on_message_expiration, _lower),
            ('DeadLetteringOnFilterEvaluationExceptions', sub.dead_lettering_on_filter_evaluation_exceptions, _lower),
            ('EnableBatchedOperations', sub.enable_batched_operations, _lower),
            ('MaxDeliveryCount', sub.max_delivery_count, None),
            ('MessageCount', sub.message_count, None),
            ])

    return _convert_object_to_feed_entry(
        sub, 'SubscriptionDescription', _subscription_to_xml)


def _convert_rule_to_xml(rule):

    def _rule_to_xml(writer, rule):
        if rule.filter_type:
            writer.start('Filter', [('i:type', rule.filter_type, None)])
            if rule.filter_type == 'CorrelationFilter':
                writer.element('CorrelationId', rule.filter_expression)
            else:
                writer.element('SqlExpression', rule.filter_expression)
                writer.element('CompatibilityLevel', '20')
            writer.end('Filter')
            pass
        if rule.action_type:
            writer.start('Action', [('i:type', rule.action_type, None)])
            if rule.action_type == 'SqlRuleAction':
                writer.element('SqlExpression', rule.action_expression)
                writer.element('CompatibilityLevel', '20')
            writer.end('Action')
            pass

    return _convert_object_to_feed_entry(
        rule, 'RuleDescription', _rule_to_xml)


def _convert_topic_to_xml(topic):

    def _topic_to_xml(writer, topic):
        writer.elements([
            ('DefaultMessageTimeToLive', topic.default_message_time_to_live, None),
            ('MaxSizeInMegabytes', topic.max_size_in_megabytes, None),
            ('RequiresDuplicateDetection', topic.requires_duplicate_detection, _lower),
            ('DuplicateDetectionHistoryTimeWindow', topic.duplicate_detection_history_time_window, None),
            ('EnableBatchedOperations', topic.enable_batched_operations, _lower),
            ('SizeInBytes', topic.size_in_bytes, None),
            ])

    return _convert_object_to_feed_entry(
        topic, 'TopicDescription', _topic_to_xml)


def _convert_queue_to_xml(queue):

    def _queue_to_xml(writer, queue):
        writer.elements([
            ('LockDuration', queue.lock_duration, None),
            ('MaxSizeInMegabytes', queue.max_size_in_megabytes, None),
            ('RequiresDuplicateDetection', queue.requires_duplicate_detection, _lower),
            ('RequiresSession', queue.requires_session, _lower),
            ('DefaultMessageTimeToLive', queue.default_message_time_to_live, None),
            ('DeadLetteringOnMessageExpiration', queue.dead_lettering_on_message_expiration, _lower),
            ('DuplicateDetectionHistoryTimeWindow', queue.duplicate_detection_history_time_window, None),
            ('MaxDeliveryCount', queue.max_delivery_count, None),
            ('EnableBatchedOperations', queue.enable_batched_operations, _lower),
            ('SizeInBytes', queue.size_in_bytes, None),
            ('MessageCount', queue.message_count, None),
            ])

    return _convert_object_to_feed_entry(
        queue, 'QueueDescription', _queue_to_xml)


def _convert_event_hub_to_xml(hub):

    def _hub_to_xml(writer, hub):
        writer.elements(
            [('MessageRetentionInDays', hub.message_retention_in_days, None)])
        if hub.authorization_rules:
            writer.start('AuthorizationRules')
            for rule in hub.authorization_rules:
                writer.start('AuthorizationRule',
                             [('i:type', 'SharedAccessAuthorizationRule', None)])
                writer.elements(
                    [('ClaimType', rule.claim_type, None),
                     ('ClaimValue', rule.claim_value, None)])
                if rule.rights:
                    writer.start('Rights')
                    for right in rule.rights:
                        writer.element('AccessRights', right)
                    writer.end('Rights')
                writer.elements(
                    [('KeyName', rule.key_name, None),
                     ('PrimaryKey', rule.primary_key, None),
                     ('SecondaryKey', rule.secondary_key, None)])
                writer.end('AuthorizationRule')
            writer.end('AuthorizationRules')
        writer.elements(
            [('Status', hub.status, None),
             ('UserMetadata', hub.user_metadata, None),
             ('PartitionCount', hub.partition_count, None)])

    return _convert_object_to_feed_entry(
        hub, 'EventHubDescription', _hub_to_xml)


def _service_bus_error_handler(http_error):
    ''' Simple error handler for service bus service. '''
    return _general_error_handler(http_error)
