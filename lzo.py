
import struct
import io
import builtins
from _lzo import *

__all__ = ["LzoFile", "open"]

MAGIC = b"\x89\x4C\x5A\x4F\x00\x0D\x0A\x1A\x0A"

READ, WRITE = 1, 2

ADLER32_INIT_VALUE = 1
CRC32_INIT_VALUE = 0


LZOP_VERSION = 0x1030
LZO_LIB_VERSION = 0x0940


BLOCK_SIZE = (128*1024)
MAX_BLOCK_SIZE = (64*1024*1024)


F_ADLER32_D     = 0x00000001
F_ADLER32_C     = 0x00000002
F_STDIN         = 0x00000004
F_STDOUT        = 0x00000008
F_NAME_DEFAULT  = 0x00000010
F_DOSISH        = 0x00000020
F_H_EXTRA_FIELD = 0x00000040
F_H_GMTDIFF     = 0x00000080
F_CRC32_D       = 0x00000100
F_CRC32_C       = 0x00000200
F_MULTIPART     = 0x00000400
F_H_FILTER      = 0x00000800
F_H_CRC32       = 0x00001000
F_H_PATH        = 0x00002000
F_MASK          = 0x00003FFF

def open(filename, mode):
    return LzoFile(filename = filename, mode = mode)

class LzoFile(io.BufferedIOBase):

    def __init__(self, filename=None, mode=None,
                 compresslevel=None, fileobj=None, mtime=None, verify_checksum=True):
        """Constructor for the LzoFile class.

        At least one of fileobj and filename must be given a
        non-trivial value.

        The compresslevel and mtime attribute is not supported so far

        The new class instance is based on fileobj, which can be a regular
        file, a StringIO object, or any other object which simulates a file.
        It defaults to None, in which case filename is opened to provide
        a file object.

        When fileobj is not None, the filename argument is only used to be
        included in the gzip file header, which may includes the original
        filename of the uncompressed file.  It defaults to the filename of
        fileobj, if discernible; otherwise, it defaults to the empty string,
        and in this case the original filename is not included in the header.


        """

        # guarantee the file is opened in binary mode on platforms
        # that care about that sort of thing
        if mode:
            if 'b' not in mode:  mode += 'b'
        else:
            mode = 'rb'

        if fileobj is None:
            fileobj = builtins.open(filename, mode)
            self.need_close = True
        else:
            self.need_close = False

        if filename is None:
            if hasattr(fileobj, 'name'): filename = fileobj.name
            else: filename = ''
        if mode is None:
            if hasattr(fileobj, 'mode'): mode = fileobj.mode
            else: mode = 'rb'

        if mode[0:1] == 'r':
            self.mode = READ

        elif mode[0:1] == 'w' or mode[0:1] == 'a':
            self.mode = WRITE

        else:
            raise IOError("Mode " + mode + " not supported")

        self.fileobj = fileobj
        self.offset = 0
        self.verify_checksum = verify_checksum

        if self.mode == READ:
            self._buf = []
            self._buf_len = 0
            self._read_magic()
            self._read_header()

        elif self.mode == WRITE:
            self.version = LZOP_VERSION
            self.libver = LZO_LIB_VERSION

            self.method = 1             # TODO: three methods
            self.level = 1

            self.flags = 0
            #self.flags|= F_OS & F_OS_MASK
            #self.flags|= F_CS & F_CS_MASK

            self.flags|= F_ADLER32_D
            self.flags|= F_ADLER32_C

            self.compress_mode = 0
            self.mtime_low = 0
            self.mtime_high = 0

            self.name = filename

            self._write_magic()
            self._write_header()

    def _clear_buf(self):
        self._buf = []
        self._buf_len = 0

    def _read_from_buf(self, size):
        assert self._buf_len >= size
        buf_read = 0
        result = []
        while self._buf:
            block = self._buf.pop(0)

            if buf_read + len(block) < size:
                buf_read += len(block)
                result.append(block)

            elif buf_read + len(block) == size:
                buf_read += len(block)
                result.append(block)
                break

            else:
                need = block[:size - buf_read]
                remain = block[size - buf_read:]

                result.append(need)

                self._clear_buf()
                self._buf.append(remain)
                self._buf_len += len(remain)
                
                break

        return b"".join(result)
    


    def _read_magic(self):
        # XXX TODO: figure out why fails
        MAGIC = b"\x89\x4C\x5A\x4F\x00\x0D\x0A\x1A\x0A"
        magic = self.fileobj.read(len(MAGIC))

        if magic == MAGIC:
            return True
        else:
            raise IOError('Wrong lzo signature')

    def _read_header(self):
        self.adler32 = ADLER32_INIT_VALUE
        self.crc32 = CRC32_INIT_VALUE

        self.version = self._read16_c()
        self.libver = self._read16_c()

        if self.version > 0x0940:
            self.ver_need_ext = self._read16_c()
            if self.ver_need_ext > LZOP_VERSION:
                raise IOError('Need liblzo version higher than %s' %(hex(self.ver_need_ext)))
            elif self.ver_need_ext < 0x0900:
                raise IOError('3')

        self.method = self._read8_c()
        assert(self.method in [1,2,3])

        if self.version >= 0x0940:
            self.level = self._read8_c()

        self.flags = self._read32_c()

        if self.flags & F_H_CRC32:
            raise error('CRC32 not implemented in minilzo')

        if self.flags & F_H_FILTER:
            self.ffilter = self._read32()

        self.compress_mode = self._read32_c()
        self.mtime_low = self._read32_c()
        if self.version >= 0x0940:
            self.mtime_high = self._read32_c()

        l = self._read8_c()
        self.name = self._read_c(l)

        checksum = self.crc32 if self.flags & F_H_CRC32 else self.adler32

        self.header_checksum = self._read32_c()
        if self.verify_checksum:
            assert checksum == self.header_checksum

        if self.flags & F_H_EXTRA_FIELD:
            l = self._read32_c()
            self.extra = self._read_c(l)
            checksum = self.crc32 if self.flags & F_H_CRC32 else self.adler32
            if self.verify_checksum:
                assert checksum == self._read32_c()

    def _read_block(self):
        dst_len = self._read32()

        if dst_len == 0:
            return None

        if dst_len > MAX_BLOCK_SIZE:
            raise error('uncompressed larger than max block size')

        src_len = self._read32()

        if self.flags & F_ADLER32_D:
            d_adler32 = self._read32()

        if self.flags & F_CRC32_D:
            d_crc32 = self._read32()

        if self.flags & F_ADLER32_C:
            if src_len < dst_len:
                c_adler32 = self._read32()
            else:
                c_adler32 = d_adler32

        if self.flags & F_CRC32_C:
            if src_len < dst_len:
                c_crc32 = self._read32()
            else:
                c_crc32 = d_crc32

        block = self.fileobj.read(src_len)


        if src_len < dst_len:
            uncompressed = decompress_block(block, dst_len)
        else:
            uncompressed = block

        if self.verify_checksum:
            if self.flags & F_ADLER32_C:
                checksum = lzo_adler32(block, ADLER32_INIT_VALUE);
                assert checksum == c_adler32

            if self.flags & F_ADLER32_D:
                checksum = lzo_adler32(uncompressed, ADLER32_INIT_VALUE);
                assert checksum == d_adler32

            # XXX TODO: CRC checksum

        return uncompressed

    def _read_c(self, n):
        bytes = self.fileobj.read(n)
        #print self.adler32
        self.adler32 = lzo_adler32(bytes, self.adler32)
        return bytes

    def _read32_c(self):
        return struct.unpack(">I", self._read_c(4))[0]

    def _read16_c(self):
        return struct.unpack(">H", self._read_c(2))[0]  

    def _read8_c(self):
        return ord(self._read_c(1))

    def _read32(self):
        return struct.unpack(">I", self.fileobj.read(4))[0]

    def _read16(self):
        return struct.unpack(">H", self.fileobj.read(2))[0]
        
    def _read8(self):
        return ord(self.fileobj.read(1))

    def _write_c(self, bytes):
        '''write with checksum, using in write header'''
        n = self.fileobj.write(bytes)
        #print hex(self.adler32)
        self.adler32 = lzo_adler32(bytes, self.adler32)
        return n

    def _write32_c(self, value):
        self._write_c(struct.pack(">I", value))

    def _write16_c(self, value):
        self._write_c(struct.pack(">H", value))

    def _write8_c(self, value):
        self._write_c(struct.pack("B", value))

    def _write32(self, value):
        self.fileobj.write(struct.pack(">I", value))

    def _write16(self, value):
        self.fileobj.write(struct.pack(">H", value))

    def _write8(self, value):
        self.fileobj.write(struct.pack("B", value))

    def _write_magic(self):
        self.fileobj.write(MAGIC)

    def _write_header(self):
        self.adler32 = ADLER32_INIT_VALUE
        self.crc32 = CRC32_INIT_VALUE

        self._write16_c(self.version)
        self._write16_c(self.libver)
        self._write16_c(0x0940)        # ver_need_ext #TODO: del magic number 

        self._write8_c(self.method)
        self._write8_c(self.level)

        self._write32_c(self.flags)

        self._write32_c(self.mode)
        self._write32_c(self.mtime_low)
        self._write32_c(self.mtime_high)

        l = len(self.name)
        assert l < 255

        self._write8_c(l)
        if l>0:
            self._write_c(self.name)

        self._write32_c(self.adler32)

    def _write_block(self, block):
        bytes_write = 0

        self._write32(len(block))

        bytes_write += 4
        if len(block) == 0:
            return bytes_write

        d_adler32 = lzo_adler32(block, ADLER32_INIT_VALUE)

        #print self.method, self.level
        compressed = compress_block(block, self.method, self.level)
        c_adler32 = lzo_adler32(compressed, ADLER32_INIT_VALUE)


        if len(compressed) < len(block):
            self._write32(len(compressed))
            self._write32(d_adler32)
            self._write32(c_adler32)
            
            self.fileobj.write(compressed)
            bytes_write += len(compressed) + 8
            return bytes_write

        else:
            self._write32(len(block))
            self._write32(d_adler32)
            self.fileobj.write(block)
            bytes_write += len(compressed) + 8
            return bytes_write


    @property
    def closed(self):
        return self.fileobj is None

    def _check_closed(self):
        """Raises a ValueError if the underlying file object has been closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

    def read(self, size=-1):
        self._check_closed()

        if self.mode != READ:
            import errno
            raise IOError(errno.EBADF, "read() on write-only GzipFile object")

        while size == -1 or self._buf_len < size:
            block = self._read_block()
            if block:
                self._buf.append(block)
                self._buf_len += len(block)
            else:
                break

        to_read = self._buf_len if size == -1 else size
        self.offset += to_read
        return self._read_from_buf(to_read)

    def write(self, content):
        bytes_write = 0
        off = 0

        while off + BLOCK_SIZE < len(content):
            block = content[off:off+BLOCK_SIZE]
            off += BLOCK_SIZE
            self._write_block(block)
            #print 1
        self._write_block(content[off:])

        #if off < len(content)
        self._write32(0)


    @property
    def closed(self):
        return self.fileobj is None

    def close(self):
        if self.fileobj is None:
            return
        
        if self.need_close:
            self.fileobj.close()

        if self.mode == READ:
            self.fileobj = None
        elif self.mode == WRITE:
            self.fileobj = None

    def fileno(self):
        """Invoke the underlying file object's fileno() method.

        This will raise AttributeError if the underlying file object
        doesn't support fileno().
        """
        return self.fileobj.fileno()

    def readable(self):
        return self.mode == READ

    def writable(self):
        return self.mode == WRITE

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        if whence:
            if whence == 1:
                offset = self.offset + offset
            else:
                raise ValueError('Seek from end not supported')
        if self.mode == WRITE:
            if offset < self.offset:
                raise IOError('Negative seek in write mode')
            count = offset - self.offset
            for i in range(count // 1024):
                self.write(1024 * '\0')
            self.write((count % 1024) * '\0')
        elif self.mode == READ:
            if offset < self.offset:
                # for negative seek, rewind and do positive seek
                self.rewind()
            count = offset - self.offset
            for i in range(count // 1024):
                self.read(1024)
            self.read(count % 1024)

        return self.offset

    def rewind(self):
        '''Return the uncompressed stream file position indicator to the
        beginning of the file'''
        if self.mode != READ:
            raise IOError("Can't rewind in write mode")
        import warnings
        warnings.warn("use rewind is slow")

        self.fileobj.seek(0)
        self._read_magic()
        self._read_header()

        self._clear_buf()
        self.offset = 0


    def __repr__(self):
        s = repr(self.fileobj)
        return '<gzip ' + s[1:-1] + ' ' + hex(id(self)) + '>'


def test():
    import os
    data = os.urandom(2*1024*1024)

    f = LzoFile(filename = 'test.lzo', mode='wb')
    f.write(data)
    f.close()
    print('write done')

    f = LzoFile(filename = 'test.lzo', mode='rb')
    part1 = f.read(1024)
    part2 = f.read(1024)
    part3 = f.read()
    f.close()
    assert data == b''.join([part1, part2, part3])

    print('test complete')

def main():
    import argparse
    import os
    parser = argparse.ArgumentParser(description='Compress or decompress like lzop')
    parser.add_argument('-d', '--decompress', dest='decompress', action='store_true')
    #parser.add_argument('-t', '--test', dest='test', action='store_true')
    parser.add_argument('path')
    args = parser.parse_args()

    filename = os.path.basename(args.path)
    if args.decompress:
        with LzoFile(filename = args.path) as f:
            name, ext = os.path.splitext(filename)
            if ext == '.lzo':
                de_name = name
            else:
                de_name = filename + '.uncompressed'

            with builtins.open(de_name, 'wb') as de:
                de.write(f.read())

    else:
        with builtins.open(args.path, 'rb') as f:
            with LzoFile(filename = args.path + ".lzo", mode = 'wb') as com:
                com.write(f.read())


if __name__ == '__main__':
    main()