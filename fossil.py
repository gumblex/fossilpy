#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import io
import time
import zlib
import struct
import sqlite3
import calendar
import warnings
import collections

__version__ = '0.3'

try:
    import numpy
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

unsigned_to_signed = lambda v: v-0x100000000 if v & 0x80000000 else v
utf8_decode = lambda b: b.decode('utf-8')
text_escape = lambda s: s.replace('\\', '\\\\').replace(' ', '\\s').replace('\n', '\\n')
text_unescape = lambda s: s.replace('\\s', ' ').replace('\\n', '\n').replace('\\\\', '\\')
parse_dt = lambda s: calendar.timegm(time.strptime(s[:19], '%Y-%m-%dT%H:%M:%S'))
julian_to_unix = lambda t: (t-2440587.5)*86400
unix_to_julian = lambda t: t/86400 + 2440587.5

def base64_putint(v):
    zdigits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~"
    if not v:
        return '0'
    ret = ''
    while v > 0:
        ret += zdigits[v&0x3f]
        v >>= 6
    return ret


def base64_getint(buf, pos=0):
    """Returns the encoded integer and consumed string length."""
    v = 0
    for z, ch in enumerate(buf[pos:]):
        c = base64_getint.zvalue[0x7f&ch]
        if c < 0:
            break
        v = (v<<6) + c
    else:
        z += 1
    return (v, pos+z)

base64_getint.zvalue = (
    -1, -1, -1, -1, -1, -1, -1, -1,   -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1,   -1, -1, -1, -1, -1, -1, -1, -1,
    -1, -1, -1, -1, -1, -1, -1, -1,   -1, -1, -1, -1, -1, -1, -1, -1,
     0,  1,  2,  3,  4,  5,  6,  7,    8,  9, -1, -1, -1, -1, -1, -1,
    -1, 10, 11, 12, 13, 14, 15, 16,   17, 18, 19, 20, 21, 22, 23, 24,
    25, 26, 27, 28, 29, 30, 31, 32,   33, 34, 35, -1, -1, -1, -1, 36,
    -1, 37, 38, 39, 40, 41, 42, 43,   44, 45, 46, 47, 48, 49, 50, 51,
    52, 53, 54, 55, 56, 57, 58, 59,   60, 61, 62, -1, -1, -1, 63, -1,
)


def decompress(blob):
    size = struct.unpack('>I', blob[:4])[0]
    orig = zlib.decompress(blob[4:])
    # not passed on pkgsrc.fossil
    # assert len(orig) == size
    return orig


if NUMPY_AVAILABLE:
    def delta_checksum(blob):
        dt = numpy.dtype(numpy.uint32)
        dt = dt.newbyteorder('>')
        m = len(blob) % 4
        array = numpy.frombuffer(bytes(blob) + (b'\0' * (4-m)), dtype=dt)
        return int(array.sum(dtype=dt))
else:
    # can't calculate efficiently using native methods
    def delta_checksum(blob):
        checksum = 0
        uint32 = 4294967296
        ints, m = divmod(len(blob), 4)
        for i in range(ints):
            checksum = (checksum + struct.unpack('>I', blob[i*4:i*4+4])[0]) % uint32
        rem = bytes(blob[ints*4:]) + (b'\0' * (4-m))
        checksum = (checksum + struct.unpack('>I', rem)[0]) % uint32
        return checksum


def delta_apply(blob, delta, check=False):
    newblob = io.BytesIO()
    mblob = memoryview(blob)
    mdelta = memoryview(delta)
    targetsize, pos = base64_getint(mdelta)
    pos += 1 # \n
    while pos < len(delta):
        num, pos = base64_getint(mdelta, pos)
        op = mdelta[pos]
        if op == 64: # @
            pos += 1
            offset, pos = base64_getint(mdelta, pos)
            pos += 1 # ,
            newblob.write(mblob[offset:offset+num])
        elif op == 58: # :
            pos += 1
            newblob.write(mdelta[pos:pos+num])
            pos += num
        elif op == 59: # ;
            checksum = num
            break
        else:
            raise ValueError('invalid delta encoding')
    else:
        raise ValueError('invalid delta encoding')
    buf = newblob.getbuffer()
    if targetsize != len(buf):
        raise ValueError('delta decoding failed, size mismatch: %d, %d' %
                         (targetsize, len(buf)))
    elif check:
        if checksum != delta_checksum(buf):
            raise ValueError('delta decoding failed, data mismatch')
    return newblob.getvalue()


def remove_clearsign(blob):
    clearsign_header = b'-----BEGIN PGP SIGNED MESSAGE-----'
    pgpsign_header = b'-----BEGIN PGP SIGNATURE-----'
    if not blob.startswith(clearsign_header):
        return blob
    lines = []
    content = False
    for k, ln in enumerate(blob.splitlines(True)):
        if not ln.rstrip():
            content = True
        elif content:
            if ln.rstrip() == pgpsign_header:
                break
            elif ln.startswith(b'- '):
                lines.append(ln[2:])
            else:
                lines.append(ln)
    return b''.join(lines)


class LRUCache(collections.UserDict):
    def __init__(self, maxlen):
        self.capacity = maxlen
        self.data = collections.OrderedDict()

    def __getitem__(self, key):
        value = self.data.pop(key)
        self.data[key] = value
        return value

    def get(self, key, default=None):
        try:
            value = self.data.pop(key)
            self.data[key] = value
            return value
        except KeyError:
            return default

    def __setitem__(self, key, value):
        if self.capacity:
            try:
                self.data.pop(key)
            except KeyError:
                if len(self.data) >= self.capacity:
                    self.data.popitem(last=False)
            self.data[key] = value


class Artifact:
    def __init__(self, blob=None, rid=None, uuid=None):
        self.blob = blob
        self.rid = rid
        self.uuid = uuid

    def __repr__(self):
        return '<Artifact rid=%r, uuid=%r>' % (self.rid, self.uuid)


class File(Artifact):
    def __repr__(self):
        return '<File rid=%r, uuid=%r>' % (self.rid, self.uuid)


class StructuralArtifact(Artifact):
    CARDTYPES = {
        'A': 'attachment',
        'B': 'baseline',
        'C': 'comment',
        'D': 'datetime',
        'E': 'technote',
        'F': 'file',
        'G': 'thread_root',
        'H': 'thread_title',
        'I': 'in_reply_to',
        'J': 'ticket_change',
        'K': 'ticket_id',
        'L': 'wiki_title',
        'M': 'manifest',
        'N': 'mimetype',
        'P': 'parent_artifact',
        'Q': 'cherry_pick',
        'R': 'repository_checksum',
        'T': 'tag',
        'U': 'user_login',
        'W': 'wiki_text',
        'Z': 'checksum'
    }
    CARDTYPES_REV = {v:k for k,v in CARDTYPES.items()}
    CARDMULTI = frozenset('FJMQT')

    def __init__(self, blob=None, rid=None, uuid=None):
        super().__init__(blob, rid, uuid)
        self.cards = {}
        self.parse()

    @classmethod
    def from_artifact(cls, artifact):
        return cls(artifact.blob, artifact.rid, artifact.uuid)

    def parse(self):
        f = io.BytesIO(remove_clearsign(self.blob))
        line = f.readline()
        while line:
            cmd, *toks = line.decode('utf-8').rstrip().split(' ')
            if cmd in 'AFJT':
                val = tuple(map(text_unescape, toks))
            elif cmd in 'BGIKMNRZ':
                val = toks[0]
            elif cmd in 'CHLU':
                val = text_unescape(toks[0])
            elif cmd == 'D':
                val = parse_dt(toks[0])
            elif cmd == 'E':
                toks[0] = parse_dt(toks[0])
                val = tuple(toks)
            elif cmd in 'PQ':
                val = tuple(toks)
            elif cmd == 'W':
                size = int(toks[0])
                val = f.read(size+1).decode('utf-8')
            else:
                raise ValueError('unrecognized card: ' + line.decode('utf-8').rstrip())
            if cmd in self.CARDMULTI:
                if cmd in self.cards:
                    self.cards[cmd].append(val)
                else:
                    self.cards[cmd] = [val]
            else:
                self.cards[cmd] = val
            line = f.readline()

    def keys(self):
        return self.cards.keys()

    def __getitem__(self, key):
        if key.upper() in self.cards:
            return self.cards[key]
        elif key in self.CARDTYPES_REV:
            return self.cards[self.CARDTYPES_REV[key]]
        else:
            raise KeyError(key)

    def __getattr__(self, key):
        return self.__getitem__(key)

    def __repr__(self):
        return '<StructuralArtifact rid=%r, uuid=%r>' % (self.rid, self.uuid)


class Repo:

    def __init__(self, repository, check=False, cachesize=64):
        self.repository = repository
        self.db = sqlite3.connect(repository)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA case_sensitive_like=1')
        if check and not NUMPY_AVAILABLE:
            warnings.warn('install numpy to calculate checksum faster')
        self.check = check
        self.cache = LRUCache(cachesize)

    def artifact(self, key, type_=None):
        '''Get an artifact by rid or uuid'''
        if isinstance(key, int):
            kwd = 'rid'
            val = key
        else:
            kwd = 'uuid'
            val = key
        blob = None
        for rid, uuid, content in self.execute(
            "WITH RECURSIVE b(rid, uuid, content, depth) AS ("
            "SELECT rid, uuid, content, 0 FROM blob WHERE %s = ? "
            "UNION ALL "
            "SELECT blob.rid, blob.uuid, blob.content, b.depth-1 "
            "FROM blob, delta, b "
            "WHERE delta.rid = b.rid AND blob.rid = delta.srcid"
            ") SELECT rid, uuid, content FROM b ORDER BY depth" % kwd, (val,)):
            if rid in self.cache:
                blob = self.cache[rid]
            else:
                if blob:
                    blob = delta_apply(blob, decompress(content), self.check)
                else:
                    blob = decompress(content)
                self.cache[rid] = blob
        if not blob:
            raise ValueError("can't find artifact: %s" % rid)
        if type_ == 'structural':
            return StructuralArtifact(blob, rid, uuid)
        elif type_ == 'file':
            return File(blob, rid, uuid)
        else:
            return Artifact(blob, rid, uuid)

    def __getitem__(self, key):
        return self.artifact(key)

    def file(self, key):
        return self.artifact(key, 'file')

    def manifest(self, key):
        return self.artifact(key, 'structural')

    def find_artifact(self, prefix):
        row = self.execute('SELECT rid, uuid FROM blob WHERE uuid LIKE ?',
              (prefix+'%',)).fetchone()
        if row:
            return tuple(row)
        else:
            raise KeyError("can't find a blob with prefix " + prefix)

    def to_uuid(self, rid):
        row = self.execute('SELECT uuid FROM blob WHERE rid = ?',
              (rid,)).fetchone()
        if row:
            return row[0]
        else:
            raise IndexError('rid %d not found' % rid)

    def to_rid(self, uuid):
        row = self.execute('SELECT rid FROM blob WHERE uuid = ?',
              (uuid,)).fetchone()
        if row:
            return row[0]
        else:
            raise IndexError('uuid %s not found' % uuid)

    def execute(self, sql, parameters=None):
        return self.db.cursor().execute(sql, parameters)
