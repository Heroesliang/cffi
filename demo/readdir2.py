# A Linux-only demo, using verify() instead of hard-coding the exact layouts
#
from cffi import FFI


ffi = FFI()
ffi.cdef("""

    typedef ... DIR;

    struct dirent {
        unsigned char  d_type;
        char           d_name[];
        ...;
    };

    int readdir_r(DIR *dirp, struct dirent *entry, struct dirent **result);
    int openat(int dirfd, const char *pathname, int flags);
    DIR *fdopendir(int fd);
    int closedir(DIR *dirp);

""")
ffi.C = ffi.verify("""
#ifndef _ATFILE_SOURCE
#  define _ATFILE_SOURCE
#endif
#include <fcntl.h>
#include <sys/types.h>
#include <dirent.h>
""")


def walk(basefd, path):
    print '{', path
    dirfd = ffi.C.openat(basefd, path, 0)
    if dirfd < 0:
        # error in openat()
        return
    dir = ffi.C.fdopendir(dirfd)
    dirent = ffi.new("struct dirent")
    result = ffi.new("struct dirent *")
    while True:
        if ffi.C.readdir_r(dir, dirent, result):
            # error in readdir_r()
            break
        if result[0] is None:
            break
        name = str(dirent.d_name)
        print '%3d %s' % (dirent.d_type, name)
        if dirent.d_type == 4 and name != '.' and name != '..':
            walk(dirfd, name)
    ffi.C.closedir(dir)
    print '}'


walk(-1, "/tmp")
