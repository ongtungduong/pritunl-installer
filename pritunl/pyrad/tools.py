# Copyright 2002-2008 Wichert Akkerman. All rights reserved.
# Copyright 2007-2008 Simplon. All rights reserved.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# 3. Neither the name of the University nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
# tools.py
#
# Utility functions
import struct
import six


def EncodeString(str):
    if len(str) > 253:
        raise ValueError('Can only encode strings of <= 253 characters')
    if isinstance(str, six.text_type):
        return str.encode('utf-8')
    else:
        return str


def EncodeOctets(str):
    if len(str) > 253:
        raise ValueError('Can only encode strings of <= 253 characters')
    return str


def EncodeAddress(addr):
    if not isinstance(addr, six.string_types):
        raise TypeError('Address has to be a string')
    (a, b, c, d) = list(map(int, addr.split('.')))
    return struct.pack('BBBB', a, b, c, d)


def EncodeInteger(num):
    if not isinstance(num, six.integer_types):
        raise TypeError('Can not encode non-integer as integer')
    return struct.pack('!I', num)


def EncodeDate(num):
    if not isinstance(num, int):
        raise TypeError('Can not encode non-integer as date')
    return struct.pack('!I', num)


def DecodeString(str):
    return str.decode('utf-8')


def DecodeOctets(str):
    return str


def DecodeAddress(addr):
    return '.'.join(map(str, struct.unpack('BBBB', addr)))


def DecodeInteger(num):
    return (struct.unpack('!I', num))[0]


def DecodeDate(num):
    return (struct.unpack('!I', num))[0]


def EncodeAttr(datatype, value):
    if datatype == 'string':
        return EncodeString(value)
    elif datatype == 'octets':
        return EncodeOctets(value)
    elif datatype == 'ipaddr':
        return EncodeAddress(value)
    elif datatype == 'integer':
        return EncodeInteger(value)
    elif datatype == 'date':
        return EncodeDate(value)
    else:
        raise ValueError('Unknown attribute type %s' % datatype)


def DecodeAttr(datatype, value):
    if datatype == 'string':
        return DecodeString(value)
    elif datatype == 'octets':
        return DecodeOctets(value)
    elif datatype == 'ipaddr':
        return DecodeAddress(value)
    elif datatype == 'integer':
        return DecodeInteger(value)
    elif datatype == 'date':
        return DecodeDate(value)
    else:
        raise ValueError('Unknown attribute type %s' % datatype)
