# Copyright 2015 Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from rally.common import logging
from rally import consts
from rally.plugins.openstack.context.manila import consts as manila_consts
from rally.plugins.openstack import scenario
from rally.plugins.openstack.scenarios.manila import utils
from rally.task import validation


"""Scenarios for Manila shares."""


@validation.validate_share_proto()
@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_and_delete_share",
                    platform="openstack")
class CreateAndDeleteShare(utils.ManilaScenario):

    def run(self, share_proto, size=1, min_sleep=0, max_sleep=0, **kwargs):
        """Create and delete a share.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between share creation and deletion
        (of random duration from [min_sleep, max_sleep]).

        :param share_proto: share protocol, valid values are NFS, CIFS,
            GlusterFS and HDFS
        :param size: share size in GB, should be greater than 0
        :param min_sleep: minimum sleep time in seconds (non-negative)
        :param max_sleep: maximum sleep time in seconds (non-negative)
        :param kwargs: optional args to create a share
        """
        share = self._create_share(
            share_proto=share_proto,
            size=size,
            **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._delete_share(share)


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(name="ManilaShares.list_shares", platform="openstack")
class ListShares(utils.ManilaScenario):

    def run(self, detailed=True, search_opts=None):
        """Basic scenario for 'share list' operation.

        :param detailed: defines either to return detailed list of
            objects or not.
        :param search_opts: container of search opts such as
            "name", "host", "share_type", etc.
        """
        self._list_shares(detailed=detailed, search_opts=search_opts)


@validation.add("enum", param_name="share_proto", values=["nfs", "cephfs",
                "cifs", "glusterfs", "hdfs"], missed=False,
                case_insensitive=True)
@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_and_extend_share",
                    platform="openstack")
class CreateAndExtendShare(utils.ManilaScenario):
    def run(self, share_proto, size=1, new_size=2, snapshot_id=None,
            description=None, metadata=None, share_network=None,
            share_type=None, is_public=False, availability_zone=None,
            share_group_id=None):
        """Create and extend a share

        :param share_proto: share protocol for new share
            available values are NFS, CIFS, CephFS, GlusterFS and HDFS.
        :param size: size in GiB
        :param new_size: new size of the share in GiB
        :param snapshot_id: ID of the snapshot
        :param description: description of a share
        :param metadata: optional metadata to set on share creation
        :param share_network: either instance of ShareNetwork or text with ID
        :param share_type: either instance of ShareType or text with ID
        :param is_public: whether to set share as public or not.
        :param availability_zone: availability zone of the share
        :param share_group_id: ID of the share group to which the share
            should belong
        """
        share = self._create_share(
            share_proto=share_proto,
            size=size,
            snapshot_id=snapshot_id,
            description=description,
            metadata=metadata,
            share_network=share_network,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id
        )
        self._extend_share(share, new_size)


@validation.add("enum", param_name="share_proto", values=["nfs", "cephfs",
                "cifs", "glusterfs", "hdfs"], missed=False,
                case_insensitive=True)
@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_and_shrink_share",
                    platform="openstack")
class CreateAndShrinkShare(utils.ManilaScenario):
    def run(self, share_proto, size=2, new_size=1, snapshot_id=None,
            description=None, metadata=None, share_network=None,
            share_type=None, is_public=False, availability_zone=None,
            share_group_id=None):
        """Create and shrink a share

        :param share_proto: share protocol for new share
            available values are NFS, CIFS, CephFS, GlusterFS and HDFS.
        :param size: size in GiB
        :param new_size: new size of the share in GiB
        :param snapshot_id: ID of the snapshot
        :param description: description of a share
        :param metadata: optional metadata to set on share creation
        :param share_network: either instance of ShareNetwork or text with ID
        :param share_type: either instance of ShareType or text with ID
        :param is_public: whether to set share as public or not.
        :param availability_zone: availability zone of the share
        :param share_group_id: ID of the share group to which the share
            should belong
        """
        share = self._create_share(
            share_proto=share_proto,
            size=size,
            snapshot_id=snapshot_id,
            description=description,
            metadata=metadata,
            share_network=share_network,
            share_type=share_type,
            is_public=is_public,
            availability_zone=availability_zone,
            share_group_id=share_group_id
        )
        self._shrink_share(share, new_size)


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_share_network_and_delete",
                    platform="openstack")
class CreateShareNetworkAndDelete(utils.ManilaScenario):

    @logging.log_deprecated_args(
        "The 'name' argument to create_and_delete_service will be ignored",
        "1.1.2", ["name"], once=True)
    def run(self, neutron_net_id=None, neutron_subnet_id=None,
            nova_net_id=None, name=None, description=None):
        """Creates share network and then deletes.

        :param neutron_net_id: ID of Neutron network
        :param neutron_subnet_id: ID of Neutron subnet
        :param nova_net_id: ID of Nova network
        :param description: share network description
        """
        share_network = self._create_share_network(
            neutron_net_id=neutron_net_id,
            neutron_subnet_id=neutron_subnet_id,
            nova_net_id=nova_net_id,
            description=description,
        )
        self._delete_share_network(share_network)


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_share_network_and_list",
                    platform="openstack")
class CreateShareNetworkAndList(utils.ManilaScenario):

    @logging.log_deprecated_args(
        "The 'name' argument to create_and_delete_service will be ignored",
        "1.1.2", ["name"], once=True)
    def run(self, neutron_net_id=None, neutron_subnet_id=None,
            nova_net_id=None, name=None, description=None,
            detailed=True, search_opts=None):
        """Creates share network and then lists it.

        :param neutron_net_id: ID of Neutron network
        :param neutron_subnet_id: ID of Neutron subnet
        :param nova_net_id: ID of Nova network
        :param description: share network description
        :param detailed: defines either to return detailed list of
            objects or not.
        :param search_opts: container of search opts such as
            "name", "nova_net_id", "neutron_net_id", etc.
        """
        self._create_share_network(
            neutron_net_id=neutron_net_id,
            neutron_subnet_id=neutron_subnet_id,
            nova_net_id=nova_net_id,
            description=description,
        )
        self._list_share_networks(
            detailed=detailed,
            search_opts=search_opts,
        )


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", admin=True)
@scenario.configure(name="ManilaShares.list_share_servers",
                    platform="openstack")
class ListShareServers(utils.ManilaScenario):

    def run(self, search_opts=None):
        """Lists share servers.

        Requires admin creds.

        :param search_opts: container of following search opts:
            "host", "status", "share_network" and "project_id".
        """
        self._list_share_servers(search_opts=search_opts)


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_security_service_and_delete",
                    platform="openstack")
class CreateSecurityServiceAndDelete(utils.ManilaScenario):

    @logging.log_deprecated_args(
        "The 'name' argument to create_and_delete_service will be ignored",
        "1.1.2", ["name"], once=True)
    def run(self, security_service_type, dns_ip=None, server=None,
            domain=None, user=None, password=None,
            name=None, description=None):
        """Creates security service and then deletes.

        :param security_service_type: security service type, permitted values
            are 'ldap', 'kerberos' or 'active_directory'.
        :param dns_ip: dns ip address used inside tenant's network
        :param server: security service server ip address or hostname
        :param domain: security service domain
        :param user: security identifier used by tenant
        :param password: password used by user
        :param description: security service description
        """
        security_service = self._create_security_service(
            security_service_type=security_service_type,
            dns_ip=dns_ip,
            server=server,
            domain=domain,
            user=user,
            password=password,
            description=description,
        )
        self._delete_security_service(security_service)


@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares."
                         "attach_security_service_to_share_network",
                    platform="openstack")
class AttachSecurityServiceToShareNetwork(utils.ManilaScenario):

    def run(self, security_service_type="ldap"):
        """Attaches security service to share network.

        :param security_service_type: type of security service to use.
            Should be one of following: 'ldap', 'kerberos' or
            'active_directory'.
        """
        sn = self._create_share_network()
        ss = self._create_security_service(
            security_service_type=security_service_type)
        self._add_security_service_to_share_network(sn, ss)


@validation.validate_share_proto()
@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.create_and_list_share",
                    platform="openstack")
class CreateAndListShare(utils.ManilaScenario):

    def run(self, share_proto, size=1, min_sleep=0, max_sleep=0, detailed=True,
            **kwargs):
        """Create a share and list all shares.

        Optional 'min_sleep' and 'max_sleep' parameters allow the scenario
        to simulate a pause between share creation and list
        (of random duration from [min_sleep, max_sleep]).

        :param share_proto: share protocol, valid values are NFS, CIFS,
            GlusterFS and HDFS
        :param size: share size in GB, should be greater than 0
        :param min_sleep: minimum sleep time in seconds (non-negative)
        :param max_sleep: maximum sleep time in seconds (non-negative)
        :param detailed: defines whether to get detailed list of shares or not
        :param kwargs: optional args to create a share
        """
        self._create_share(share_proto=share_proto, size=size, **kwargs)
        self.sleep_between(min_sleep, max_sleep)
        self._list_shares(detailed=detailed)


@validation.add("number", param_name="sets", minval=1, integer_only=True)
@validation.add("number", param_name="set_size", minval=1, integer_only=True)
@validation.add("number", param_name="key_min_length", minval=1, maxval=256,
                integer_only=True)
@validation.add("number", param_name="key_max_length", minval=1, maxval=256,
                integer_only=True)
@validation.add("number", param_name="value_min_length", minval=1, maxval=1024,
                integer_only=True)
@validation.add("number", param_name="value_max_length", minval=1, maxval=1024,
                integer_only=True)
@validation.add("required_services", services=[consts.Service.MANILA])
@validation.add("required_platform", platform="openstack", users=True)
@validation.add("required_contexts",
                contexts=manila_consts.SHARES_CONTEXT_NAME)
@scenario.configure(context={"cleanup": ["manila"]},
                    name="ManilaShares.set_and_delete_metadata",
                    platform="openstack")
class SetAndDeleteMetadata(utils.ManilaScenario):

    def run(self, sets=10, set_size=3, delete_size=3,
            key_min_length=1, key_max_length=256,
            value_min_length=1, value_max_length=1024):
        """Sets and deletes share metadata.

        This requires a share to be created with the shares
        context. Additionally, ``sets * set_size`` must be greater
        than or equal to ``deletes * delete_size``.

        :param sets: how many set_metadata operations to perform
        :param set_size: number of metadata keys to set in each
            set_metadata operation
        :param delete_size: number of metadata keys to delete in each
            delete_metadata operation
        :param key_min_length: minimal size of metadata key to set
        :param key_max_length: maximum size of metadata key to set
        :param value_min_length: minimal size of metadata value to set
        :param value_max_length: maximum size of metadata value to set
        """
        shares = self.context.get("tenant", {}).get("shares", [])
        share = shares[self.context["iteration"] % len(shares)]

        keys = self._set_metadata(
            share=share,
            sets=sets,
            set_size=set_size,
            key_min_length=key_min_length,
            key_max_length=key_max_length,
            value_min_length=value_min_length,
            value_max_length=value_max_length)

        self._delete_metadata(share=share, keys=keys, delete_size=delete_size)
