import pytest
try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ImportError as e:
    def test_types():
        pytest.skip(str(e))
else:

    from cffi import FFI
    import random
    from .test_recompiler import verify

    ALL_PRIMITIVES = [
        'unsigned char',
        'short',
        'int',
        'long',
        'long long',
        'float',
        'double',
        'long double',
    ]
    def _make_struct(s):
        return st.lists(s, min_size=1)
    types = st.one_of(st.sampled_from(ALL_PRIMITIVES),
                      st.lists(st.sampled_from(ALL_PRIMITIVES), min_size=1))
    # NB. 'types' could be st.recursive instead, but it doesn't
    # really seem useful

    def draw_primitive(ffi, typename):
        value = random.random() * 2**40
        if typename != 'long double':
            return ffi.cast(typename, value)
        else:
            return value

    TEST_RUN_COUNTER = 0


    @given(st.lists(types), types)
    @settings(max_examples=20)
    def test_types(tp_args, tp_result):
        global TEST_RUN_COUNTER
        cdefs = []
        structs = {}

        def build_type(tp):
            if type(tp) is list:
                field_types = [build_type(tp1) for tp1 in tp]
                fields = ['%s f%d;' % (ftp, j)
                          for (j, ftp) in enumerate(field_types)]
                fields = '\n    '.join(fields)
                name = 's%d' % len(cdefs)
                cdefs.append("typedef struct {\n    %s\n} %s;" % (fields, name))
                structs[name] = field_types
                return name
            else:
                return tp

        args = [build_type(tp) for tp in tp_args]
        result = build_type(tp_result)

        TEST_RUN_COUNTER += 1
        signature = "%s testfargs(%s)" % (result,
            ', '.join(['%s a%d' % (arg, i) for (i, arg) in enumerate(args)])
            or 'void')

        source = list(cdefs)

        cdefs.append("%s;" % signature)
        cdefs.append("extern %s testfargs_result;" % result)
        for i, arg in enumerate(args):
            cdefs.append("extern %s testfargs_arg%d;" % (arg, i))
        source.append("%s testfargs_result;" % result)
        for i, arg in enumerate(args):
            source.append("%s testfargs_arg%d;" % (arg, i))
        source.append(signature)
        source.append("{")
        for i, arg in enumerate(args):
            source.append("    testfargs_arg%d = a%d;" % (i, i))
        source.append("    return testfargs_result;")
        source.append("}")

        ffi = FFI()
        ffi.cdef("\n".join(cdefs))
        lib = verify(ffi, 'test_function_args_%d' % TEST_RUN_COUNTER,
                     "\n".join(source), no_cpp=True)

        def make_arg(tp):
            if tp in structs:
                return [make_arg(tp1) for tp1 in structs[tp]]
            else:
                return draw_primitive(ffi, tp)

        passed_args = [make_arg(arg) for arg in args]
        returned_value = make_arg(result)

        def write(p, v):
            if type(v) is list:
                for i, v1 in enumerate(v):
                    write(ffi.addressof(p, 'f%d' % i), v1)
            else:
                p[0] = v

        write(ffi.addressof(lib, 'testfargs_result'), returned_value)

        ## CALL forcing libffi
        received_return = ffi.addressof(lib, 'testfargs')(*passed_args)
        ##

        _tp_long_double = ffi.typeof("long double")
        def check(p, v):
            if type(v) is list:
                for i, v1 in enumerate(v):
                    check(ffi.addressof(p, 'f%d' % i), v1)
            else:
                if ffi.typeof(p).item is _tp_long_double:
                    assert ffi.cast("double", p[0]) == v
                else:
                    assert p[0] == v

        for i, arg in enumerate(passed_args):
            check(ffi.addressof(lib, 'testfargs_arg%d' % i), arg)

        ret = ffi.new(result + "*", received_return)
        check(ret, returned_value)
