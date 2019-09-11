# coding=utf-8
# --------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
#
# Code generated by Microsoft (R) AutoRest Code Generator.
# Changes may cause incorrect behavior and will be lost if the code is
# regenerated.
# --------------------------------------------------------------------------

from .resource import Resource


class VirtualMachineScaleSet(Resource):
    """Describes a Virtual Machine Scale Set.

    Variables are only populated by the server, and will be ignored when
    sending a request.

    All required parameters must be populated in order to send to Azure.

    :ivar id: Resource Id
    :vartype id: str
    :ivar name: Resource name
    :vartype name: str
    :ivar type: Resource type
    :vartype type: str
    :param location: Required. Resource location
    :type location: str
    :param tags: Resource tags
    :type tags: dict[str, str]
    :param sku: The virtual machine scale set sku.
    :type sku: ~azure.mgmt.compute.v2018_04_01.models.Sku
    :param plan: Specifies information about the marketplace image used to
     create the virtual machine. This element is only used for marketplace
     images. Before you can use a marketplace image from an API, you must
     enable the image for programmatic use.  In the Azure portal, find the
     marketplace image that you want to use and then click **Want to deploy
     programmatically, Get Started ->**. Enter any required information and
     then click **Save**.
    :type plan: ~azure.mgmt.compute.v2018_04_01.models.Plan
    :param upgrade_policy: The upgrade policy.
    :type upgrade_policy: ~azure.mgmt.compute.v2018_04_01.models.UpgradePolicy
    :param virtual_machine_profile: The virtual machine profile.
    :type virtual_machine_profile:
     ~azure.mgmt.compute.v2018_04_01.models.VirtualMachineScaleSetVMProfile
    :ivar provisioning_state: The provisioning state, which only appears in
     the response.
    :vartype provisioning_state: str
    :param overprovision: Specifies whether the Virtual Machine Scale Set
     should be overprovisioned.
    :type overprovision: bool
    :ivar unique_id: Specifies the ID which uniquely identifies a Virtual
     Machine Scale Set.
    :vartype unique_id: str
    :param single_placement_group: When true this limits the scale set to a
     single placement group, of max size 100 virtual machines.
    :type single_placement_group: bool
    :param zone_balance: Whether to force strictly even Virtual Machine
     distribution cross x-zones in case there is zone outage.
    :type zone_balance: bool
    :param platform_fault_domain_count: Fault Domain count for each placement
     group.
    :type platform_fault_domain_count: int
    :param proximity_placement_group: Specifies information about the
     proximity placement group that the virtual machine scale set should be
     assigned to. <br><br>Minimum api-version: 2018-04-01.
    :type proximity_placement_group:
     ~azure.mgmt.compute.v2018_04_01.models.SubResource
    :param identity: The identity of the virtual machine scale set, if
     configured.
    :type identity:
     ~azure.mgmt.compute.v2018_04_01.models.VirtualMachineScaleSetIdentity
    :param zones: The virtual machine scale set zones.
    :type zones: list[str]
    """

    _validation = {
        'id': {'readonly': True},
        'name': {'readonly': True},
        'type': {'readonly': True},
        'location': {'required': True},
        'provisioning_state': {'readonly': True},
        'unique_id': {'readonly': True},
    }

    _attribute_map = {
        'id': {'key': 'id', 'type': 'str'},
        'name': {'key': 'name', 'type': 'str'},
        'type': {'key': 'type', 'type': 'str'},
        'location': {'key': 'location', 'type': 'str'},
        'tags': {'key': 'tags', 'type': '{str}'},
        'sku': {'key': 'sku', 'type': 'Sku'},
        'plan': {'key': 'plan', 'type': 'Plan'},
        'upgrade_policy': {'key': 'properties.upgradePolicy', 'type': 'UpgradePolicy'},
        'virtual_machine_profile': {'key': 'properties.virtualMachineProfile', 'type': 'VirtualMachineScaleSetVMProfile'},
        'provisioning_state': {'key': 'properties.provisioningState', 'type': 'str'},
        'overprovision': {'key': 'properties.overprovision', 'type': 'bool'},
        'unique_id': {'key': 'properties.uniqueId', 'type': 'str'},
        'single_placement_group': {'key': 'properties.singlePlacementGroup', 'type': 'bool'},
        'zone_balance': {'key': 'properties.zoneBalance', 'type': 'bool'},
        'platform_fault_domain_count': {'key': 'properties.platformFaultDomainCount', 'type': 'int'},
        'proximity_placement_group': {'key': 'properties.proximityPlacementGroup', 'type': 'SubResource'},
        'identity': {'key': 'identity', 'type': 'VirtualMachineScaleSetIdentity'},
        'zones': {'key': 'zones', 'type': '[str]'},
    }

    def __init__(self, **kwargs):
        super(VirtualMachineScaleSet, self).__init__(**kwargs)
        self.sku = kwargs.get('sku', None)
        self.plan = kwargs.get('plan', None)
        self.upgrade_policy = kwargs.get('upgrade_policy', None)
        self.virtual_machine_profile = kwargs.get('virtual_machine_profile', None)
        self.provisioning_state = None
        self.overprovision = kwargs.get('overprovision', None)
        self.unique_id = None
        self.single_placement_group = kwargs.get('single_placement_group', None)
        self.zone_balance = kwargs.get('zone_balance', None)
        self.platform_fault_domain_count = kwargs.get('platform_fault_domain_count', None)
        self.proximity_placement_group = kwargs.get('proximity_placement_group', None)
        self.identity = kwargs.get('identity', None)
        self.zones = kwargs.get('zones', None)