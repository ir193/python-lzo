/* 
 */

#include <Python.h>
#include "minilzo.h"

/* Ensure we have updated versions */
#if !defined(PY_VERSION_HEX) || (PY_VERSION_HEX < 0x010502f0)
#  error "Need Python version 1.5.2 or greater"
#endif

#undef UNUSED
#define UNUSED(var)     ((void)&var)

static PyObject *LzoError;

#define BLOCK_SIZE        (256*1024l)

static /* const */ char decompress__doc__[] =
"decompress(string) -- Decompress the data in string, returning a string containing the decompressed data.\n"
;

static PyObject *
decompress(PyObject *dummy, PyObject *args)
{
  PyObject *result_str;
  lzo_uint len;
  int err;
  lzo_bytep out;

  lzo_bytep in;
  lzo_uint in_len;
  UNUSED(dummy);

  if (!PyArg_ParseTuple(args, "s#", &in, &in_len))
    return NULL;


  out = (lzo_bytep) malloc(BLOCK_SIZE);
  if (out == NULL)  return PyErr_NoMemory();

  err = lzo1x_decompress_safe(in, in_len, out, &len, NULL);
  //r = lzo1x_decompress_safe(fin, 690, out, &len, NULL);
  if (err != LZO_E_OK){
      printf("internal error - decompression failed: %d\n", err);
      PyErr_SetString(LzoError, "internal error - decompression failed");
      free(out);
      return NULL;
  }
  result_str = PyString_FromStringAndSize(out, len);
  return result_str;

}
static PyObject *
decompress_block(PyObject *dummy, PyObject *args)
{
  PyObject *result;
  lzo_uint len;
  int err;
  lzo_bytep out;

  lzo_bytep in;
  lzo_uint in_len;
  lzo_uint dst_len;
  UNUSED(dummy);
  
  //should dst_len be uint?
  if (!PyArg_ParseTuple(args, "s#I", &in, &in_len, &dst_len))
    return NULL;

  result = PyBytes_FromStringAndSize(NULL, dst_len);
  if (result == NULL) {
    return NULL;
  }

    
  out = (lzo_bytep) PyBytes_AS_STRING(result);

  err = lzo1x_decompress_safe(in, in_len, out, &len, NULL);

  //r = lzo1x_decompress_safe(fin, 690, out, &len, NULL);
  if (err != LZO_E_OK){
      Py_DECREF(result);
      result = NULL;
      PyErr_SetString(LzoError, "internal error - decompression failed");
      return NULL;
  }
  if (len != dst_len){
    return NULL;
  }

  return result;

}

static PyObject *
py_lzo_adler32(PyObject *dummy, PyObject *args)
{
  lzo_uint32 value;
  lzo_bytep in;
  lzo_uint32 len;

  lzo_uint32 new;

  if (!PyArg_ParseTuple(args, "Is#", &value, &in, &len))
    return NULL;

  if(len>0){
    new = lzo_adler32(value, (const lzo_bytep)in, len);
  }

  return Py_BuildValue("I", new);
}

#ifdef USE_LIBLZO
static PyObject *
py_lzo_crc32(PyObject *dummy, PyObject *args)
{


  lzo_uint32 value;
  lzo_bytep in;
  lzo_uint32 len;

  lzo_uint32 new;

  if (!PyArg_ParseTuple(args, "Is#", &value, &in, &len))
    return NULL;
  
  if(len>0){
    new = lzo_crc32(value, (const lzo_bytep)in, len);
  }

  return Py_BuildValue("I", new);
}
#endif

/***********************************************************************
// main
************************************************************************/

static /* const */ PyMethodDef methods[] =
{
//    {"adler32",    (PyCFunction)adler32,    METH_VARARGS, adler32__doc__},
    {"decompress", (PyCFunction)decompress, METH_VARARGS, decompress__doc__},
    {"decompress_block", (PyCFunction)decompress_block, METH_VARARGS, decompress__doc__},
    {"lzo_adler32", (PyCFunction)py_lzo_adler32, METH_VARARGS, decompress__doc__},
#ifdef USE_LIBLZO
    {"lzo_crc32", (PyCFunction)py_lzo_crc32, METH_VARARGS, decompress__doc__},
#endif
    {NULL, NULL, 0, NULL}
};


static /* const */ char module_documentation[]=
"The functions in this module allow compression and decompression "
"using the LZO library.\n\n"

;


#ifdef _MSC_VER
_declspec(dllexport)
#endif
void init_lzo(void)
{
    PyObject *m, *d, *v;
    if (lzo_init() != LZO_E_OK)
    {
        return;
    }

    m = Py_InitModule4("_lzo", methods, module_documentation,
                       NULL, PYTHON_API_VERSION);
    d = PyModule_GetDict(m);

    LzoError = PyErr_NewException("_lzo.error", NULL, NULL);
    PyDict_SetItemString(d, "error", LzoError);

    v = PyString_FromString("<iridiummx@gmail.com>");
    PyDict_SetItemString(d, "__author__", v);
    Py_DECREF(v);

    v = PyInt_FromLong(LZO_VERSION);
    PyDict_SetItemString(d, "LZO_VERSION", v);
    Py_DECREF(v);
    v = PyString_FromString(LZO_VERSION_STRING);
    PyDict_SetItemString(d, "LZO_VERSION_STRING", v);
    Py_DECREF(v);
    v = PyString_FromString(LZO_VERSION_DATE);
    PyDict_SetItemString(d, "LZO_VERSION_DATE", v);
    Py_DECREF(v);
}


/*
vi:ts=4:et
*/
