# -*- coding: utf-8 -*-
#
# Copyright © 2007  Red Hat, Inc. All rights reserved.
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
# Red Hat Author(s): Luke Macken <lmacken@redhat.com>
#                    Toshio Kuratomi <tkuratom@redhat.com>
#

'''
fedora.client is used to interact with Fedora Services.

.. moduleauthor:: Ricky Zhou <ricky@fedoraproject.org>
.. moduleauthor:: Luke Macken <lmacken@redhat.com>
.. moduleauthor:: Toshio Kuratomi <tkuratom@redhat.com>

'''
class FedoraClientError(Exception):
    '''Base Exception for problems which originate within the Clients.

    Problems returned via the Services should be returned via a
    `FedoraServiceError` instead.
    '''
    pass

class FedoraServiceError(Exception):
    '''Base Exception for any problem talking with the Service.'''
    pass

class ServerError(FedoraServiceError):
    '''Unable to talk to the server properly.'''
    pass

class AuthError(FedoraServiceError):
    '''Error during authentication.  For instance, invalid password.'''
    pass

class AppError(FedoraServiceError):
    '''Error condition that the server is passing back to the client.'''
    def __init__(self, name, message, extras=None):
        self.name = name
        self.message = message
        self.extras = extras

class DictContainer(dict):
    '''dict whose members can be accessed via attribute lookup.

    One thing to note: You can have an entry in your container that is visible
    instead of a standard dict method.  So, for instance, you can have this
    happen::

        >>> d = DictContainer({'keys': 'key'})
        >>> d.keys()
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
        TypeError: 'str' object is not callable

    So, as a safety precaution, you should be sure to access things via the
    dict methods::

        >>> d = DictContainer({'keys': 'key'})
        >>> dict.keys(d)
        ['keys']

    The special methods like __getitem__(), __getattr__(), setattr(), etc
    that are invoked through alternate syntax rather than called directly as
    a method are immune to this so you can do this with no ill effects::

        >>> d.__setattr__ = 1000
        >>> d.__getattr__ = 10
        >>> print d.__setattr__
        1000
        >>> print d.__getattr__
        10
    '''
    def __getitem__(self, key):
        '''Return the value for the key in the dictionary.

        If the value is a dict, convert it to a DictContainer first.
        '''
        value = super(DictContainer, self).__getitem__(key)
        if type(value) == dict:
            value = DictContainer(value)
            self[key] = value
        return value

    def __getattribute__(self, key):
        '''Return the value from the dictionary or from the real attributes.

        * If the key exists in the dict
            * If the value is a dict
                * Convert it to a DictContainer
            * Return the converted value
        * Otherwise, if it exists in the values, return that.
        * Otherwise, raise AttributeError.
        '''
        if key in self:
            value = super(DictContainer, self).__getitem__(key)
            if type(value) == dict:
                value = DictContainer(value)
                self[key] = value
            return value
        return super(DictContainer, self).__getattribute__(key)

    def __setattr__(self, key, value):
        '''Set a key to a value.

        If the key is not an existing value, set it into the dict instead of
        as an attribute.
        '''
        if hasattr(self, key) and key not in self:
            super(DictContainer, self).__setattr__(key, value)
        else:
            self[key] = value

# We want people to be able to import fedora.client.*Client directly
# pylint: disable-msg=W0611
from fedora.client.proxyclient import ProxyClient
from fedora.client.baseclient import BaseClient
from fedora.client.fas2 import AccountSystem, FASError, CLAError
from fedora.client.pkgdb import PackageDB, PackageDBError
from fedora.client.bodhi import BodhiClient, BodhiClientException
# pylint: enable-msg=W0611

import sys
sys.modules['fedora.client.ProxyClient'] = ProxyClient
sys.modules['fedora.client.AccountSystem'] = AccountSystem
__all__ = ('FedoraServiceError', 'ServerError', 'AuthError', 'AppError',
        'FedoraClientError', 'DictContainer',
        'FASError', 'CLAError', 'BodhiClientException', 'PackageDBError',
        'ProxyClient', 'BaseClient', 'AccountSystem', 'PackageDB',
        'BodhiClient')
