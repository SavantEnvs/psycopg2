/* libFuzzer harness that embeds CPython and feeds each input to mayhem/harness_impl.py:<IMPL>(bytes).
 * The psycopg2 C extension (built with the sanitizer + SanCov flags) is loaded into the embedded
 * interpreter, so libFuzzer sees coverage of psycopg/ C sources and ASan/UBSan check its memory. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <stdlib.h>

#ifndef IMPL
#error "define IMPL to the harness_impl.py function name"
#endif

static PyObject *impl_func;

int LLVMFuzzerInitialize(int *argc, char ***argv) {
    (void)argc; (void)argv;
    Py_InitializeEx(0);
    if (PyRun_SimpleString("import sys; sys.path[:0] = ['/mayhem/build/lib', '/mayhem/mayhem']") != 0)
        abort();
    PyObject *mod = PyImport_ImportModule("harness_impl");
    if (!mod) { PyErr_Print(); abort(); }
    impl_func = PyObject_GetAttrString(mod, IMPL);
    if (!impl_func) { PyErr_Print(); abort(); }
    Py_DECREF(mod);
    return 0;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    PyObject *arg = PyBytes_FromStringAndSize((const char *)data, (Py_ssize_t)size);
    if (!arg) abort();
    PyObject *res = PyObject_CallOneArg(impl_func, arg);
    Py_DECREF(arg);
    if (!res) {
        /* harness_impl catches every outcome psycopg2 documents; anything left is a finding. */
        PyErr_Print();
        abort();
    }
    Py_DECREF(res);
    return 0;
}
