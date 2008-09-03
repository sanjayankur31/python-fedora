# -*- coding: utf-8 -*-
#
# Copyright © 2008  Red Hat, Inc. All rights reserved.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.  You should have
# received a copy of the GNU General Public License along with this program;
# if not, write to the Free Software Foundation, Inc., 51 Franklin Street,
# Fifth Floor, Boston, MA 02110-1301, USA. Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#
# Author(s): Toshio Kuratomi <tkuratom@redhat.com>
# Author(s): Mike Watters <valholla@fedoraproject.org>
#
'''Module to provide a library interface to the package database.

.. moduleauthor:: Toshio Kuratomi <tkuratom@redhat.com>
.. moduleauthor:: Mike Watters <valholla@fedoraproject.org>
'''

import simplejson

from fedora import __version__
from fedora.client import BaseClient


COLLECTIONMAP = {'F': 'Fedora',
    'FC': 'Fedora',
    'EL': 'Fedora EPEL',
    'EPEL': 'Fedora EPEL',
    'OLPC': 'Fedora OLPC',
    'RHL': 'Red Hat Linux'}

class PackageDBError(Exception):
    pass

class PackageDB(BaseClient):
    '''Provide an easy to use interface to the PackageDB.'''
    def __init__(self, base_url='https://admin.fedoraproject.org/pkgdb/',
            *args, **kwargs):
        '''Create the PackageDBClient.

        :kwarg base_url: Base of every URL used to contact the server.
            Defaults to the Fedora PackageDB instance.
        :kwarg useragent: useragent string to use.  If not given, default to
            "Fedora PackageDB Client/VERSION"
        :kwarg debug: If True, log debug information
        :kwarg username: username for establishing authenticated connections
        :kwarg password: password to use with authenticated connections
        :kwarg session_id: user's session_id to connect to the server
        :kwarg session_cookie: **Deprecated** use session_id instead.
            user's session_cookie to connect to the server
        :kwarg cache_session: if set to true, cache the user's session cookie
            on the filesystem between runs.
        '''
        if 'useragent' not in kwargs:
            kwargs['useragent'] = 'Fedora PackageDB Client/%s' % __version__
        super(PackageDBClient, self).__init__(base_url, *args, **kwargs)

    def get_package_info(self, pkgName, branch=None):
        '''Get information about the package.'''
        data = None
        if branch:
            collection, ver = canonical_branch_name(branch)
            data = {'collectionName': collection, 'collectionVersion': ver}
        pkgInfo = self.send_request('/packages/name/%s' % pkgName, req_params=data)

        return pkgInfo

    def clone_branch(self, pkg, master, owner, description, branches, ccList, coMaintList, groups):
        '''Set a branch's permissions from a pre-existing branch.
        '''

        if groups or coMaintList or ccList or description or owner:
            # Set the updated information on the master branch first
            self.add_edit_packages(pkg, owner, description, [master], ccList,
                    coMaintList, groups)

        # Get information on the master branch
        pkgInfo = self.get_package_info(pkg, master)
        if pkgInfo.has_key('message'):
            raise PackageDBError, '%s has no %s branch; cannot clone from it' % (pkg, master)
        pkgdbStatus = pkgInfo['statusMap']
        pkgInfo = pkgInfo['packageListings'][0]

        # Make sure the master branch is not in the list of branches to change
        try:
            del branches[branches.index(master)]
        except ValueError, e:
            # Exception means it wasn't there to begin with
            pass

        # Change groupList into the format the server is expecting
        groupList = {}
        for group in pkgInfo['groups']:
            if group['aclOrder']['commit'] and \
                    pkgdbStatus[str(group['aclOrder']['commit']['statuscode'])] == 'Approved':
                groupList[group['name']] = True
            else:
                groupList[group['name']] = False

        # Set all the branches to have the new branch information
        self.add_edit_package(pkg,
                pkgInfo['owneruser'],
                None, branches, None, None, groupList)

        # All acls that we want to end up on the new branch
        aclChanges = {}
        for branch in branches:
            aclChanges[branch] = {}
            for person in pkgInfo['people']:
                personAcls = {}
                aclChanges[branch][person['userid']] = personAcls
                for acl in person['aclOrder']:
                    if person['aclOrder'][acl]:
                        personAcls[acl] = pkgdbStatus[str(person['aclOrder'][acl]['statuscode'])]

        #
        # Scan through each branch to remove acls that are set but need to be
        # removed and to not set acls that already correct in the pkgdb
        #

        # Get updated package info
        branchIds = {} # PackageListingIds
        allPkgInfo = self.get_package_info(pkg)
        for pkgListing in allPkgInfo['packageListings']:
            if pkgListing['collection']['branchname'] in branches:
                # Branch we're interested in
                branch = pkgListing['collection']['branchname']
                branchIds[branch] = pkgListing['id']
                ### We are here
                for person in pkgListing['people']:
                    try:
                        personAcls = aclChanges[branch][person['userid']]
                    except KeyError:
                        # person should not have an acl in the cloned entry
                        personAcls = {}
                        aclChanges[branch][person['userid']] = personAcls
                        # If a person's  acls weren't Obsolete before, make them so now.
                        for acl in person['aclOrder']:
                            if person['aclOrder'][acl] and pkgdbStatus[str(person['aclOrder'][acl]['statuscode'])] != 'Obsolete':
                                personAcls[acl] = 'Obsolete'
                    else:
                        for acl in person['aclOrder']:
                            if not person['aclOrder'][acl]:
                                # Was unspecified before and...
                                if acl not in personAcls or not personAcls[acl] or personAcls[acl] ==  'Obsolete':
                                    # Unspecified or obsolete now, no need to set it to Obsolete
                                    try:
                                        del personAcls[acl]
                                    except KeyError:
                                        # Already unset
                                        pass
                                # Otherwise we need to set it
                                pass
                            elif acl not in personAcls:
                                # Was not obsolete before, need to Obsolete this acl now
                                personAcls[acl] = 'Obsolete'
                            else:
                                # If the status is already correct, no need to set it again
                                statuscode = str(person['aclOrder'][acl]['statuscode'])
                                if pkgdbStatus.has_key(statuscode) and pkgdbStatus[statuscode] == personAcls[acl]:
                                    del personAcls[acl]
                                # Otherwise we need to set it
                                pass

        del allPkgInfo

        # Actually set acl information now
        # acl information needs to be set separately as the compat interface
        # add_edit_packages is using can't handle the complexity
        for branch in aclChanges:
            for person in aclChanges[branch]:
                for acl in aclChanges[branch][person]:
                    data = {'pkgid': branchIds[branch],
                            'personid': person,
                            'new_acl': acl,
                            'statusname': aclChanges[branch][person][acl]}
                    response = self.send_request( '/packages/dispatcher/set_acl_status', auth=True, req_params=data)
                    if response.has_key('status') and not response['status']:
                        raise PackageDBError, 'PackageDB returned an error while setting acls for %s on %s' % (data['personid'], data['pkgid'],)

    def add_edit_package(self, pkg, owner, description, branches, ccList, coMaintList, groups):
        '''Add a new package to the database.
        '''
        # Check if the package exists
        pkgInfo = self.get_package_info(pkg)
        if pkgInfo.has_key('message'):
            # Package doesn't exist yet.  See if we have the information to
            # create it
            if owner:
                if 'devel' not in branches:
                    # automatically add a devel branch to new packages
                    branches.append('devel')

                data = {'package': pkg, 'owner': owner, 'summary': description}
                # This call creates the package and an initial branch for
                # Fedora devel
                response = self.send_request('/packages/dispatcher/add_package', auth=True, req_params=data)
                if response.has_key('message'):
                    raise PackageDBError, 'Package Database returned an error creating %s: %s' % (pkg, response['message'])
                owner = None
                description = None
            else:
                raise PackageDBError, 'Package %s does not exist and we do not have enough information to create it.' % pkg

        # Change the branches, owners, or anything else that needs changing
        data = {}
        if owner:
            data['owner'] = owner
        if description:
            data['summary'] = description
        if ccList:
            data['ccList'] = simplejson.dumps(ccList)
        if coMaintList:
            data['comaintList'] = simplejson.dumps(coMaintList)

        # Parse the groups information
        if groups:
            data['groups'] = simplejson.dumps(groups)

        # Parse the Branch abbreviations into collections
        if branches:
            data['collections'] = {}
        for branch in branches:
            collection, version = canonical_branch_name(branch)
            # Create branch
            try:
                data['collections'][collection].append(version)
            except KeyError:
                data['collections'][collection] = [version]

        # Transform the collections dict into JSON.
        data['collections'] = simplejson.dumps(data['collections'])

        # Request the changes
        response = self.send_request('/packages/dispatcher/edit_package/%s' % pkg, auth=True, req_params=data)
        if not response['status']:
            raise PackageDBError('Unable to save all information for %s: %s' % (pkg, response['message']))

    def canonical_branch_name(branch):
        '''Change a branch abbreviation into a name and version.

        Example:
        >>> name, version = canonical_branch_name('FC-6')
        >>> name
        Fedora
        >>> version
        6
        '''
        if branch == 'devel':
            collection = 'Fedora'
            version = 'devel'
        else:
            collection, version = branch.split('-')
        try:
            collection = COLLECTIONMAP[collection]
        except KeyError:
            raise KeyError, 'Collection abbreviation %s is unknown.  Use F, FC, EL, or OLPC' % collection
        
        return collection, version


    def get_owners(self, package, collection=None, collection_ver=None):
        '''Retrieve the ownership information for a package.

        URL: Same information as /packages/name/%s

        :arg package: Name of the package to retrieve package information about.
        :kwarg collection: Limit the returned information to this collection
            ('Fedora', 'Fedora EPEL', Fedora OLPC', etc)
        :kwarg collection_ver: If collection is specified, further limit to this
            version of the collection.

        :return: dict of ownership information for the package
        :rtype: dict of ownership information for the package
        '''
        method = '/packages/name/%s' % package
        if collection:
            method = method + '/' + collection
            if collection_ver:
                method = method + '/' + collection_ver
        ###FIXME: Really should reformat the data so we show either a
        # dict keyed by collection + version or
        # list of collection, version, owner
        return self.send_request(method)
