/* 
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "minilzo.h"

/* Ensure we have updated versions 
#if !defined(PY_VERSION_HEX) || (PY_VERSION_HEX < 0x010502f0)
#  error "Need Python version 1.5.2 or greater"
#endif
*/


#undef UNUSED
#define UNUSED(var)     ((void)&var)

static PyObject *LzoError;

#define BLOCK_SIZE        (256*1024l)

#define M_LZO1X_1 1
#define M_LZO1X_1_15 2
#define M_LZO1X_999 3

static /* const */ char compress__doc__[] =
"compress one block, the block is splitted in python and should be lower than BLOCK_SIZE\n"
;
static /* const */ char decompress__doc__[] =
"decompress one block, the uncompressed size should be passed as second argument (which is know when parsing lzop structure)\n"
;
static /* const */ char lzo_adler32__doc__[] =
"adler32 checksum.\n"
;


static PyObject *
compress_block(PyObject *dummy, PyObject *args)
{
  PyObject *result;
  lzo_voidp wrkmem = NULL;

  const lzo_bytep in;
  Py_ssize_t in_len;

  lzo_bytep out;
  Py_ssize_t out_len;
  Py_ssize_t new_len;

  lzo_uint32_t wrk_len;

  int level;
  int method;
  int err;
  UNUSED(dummy);

  if (!PyArg_ParseTuple(args, "s#II", &in, &in_len, &method, &level))
    return NULL;

  out_len = in_len + in_len / 64 + 16 + 3;

  if (method == M_LZO1X_1)
      wrk_len = LZO1X_1_MEM_COMPRESS;
#ifdef USE_LIBLZO
  else if (method == M_LZO1X_1_15)
      wrk_len = LZO1X_1_15_MEM_COMPRESS;
  else if (method == M_LZO1X_999)
      wrk_len = LZO1X_999_MEM_COMPRESS;
#endif


  assert(wrk_len <= WRK_LEN);

  wrkmem = (lzo_voidp) PyMem_Malloc(wrk_len);
  out = (lzo_bytep) PyMem_Malloc(out_len);
  
  if (method == M_LZO1X_1){
    err = lzo1x_1_compress(in, (lzo_uint) in_len, out, (lzo_uint*) &new_len, wrkmem);
  }
#ifdef USE_LIBLZO
  else if (method == M_LZO1X_1_15){
    err = lzo1x_1_15_compress(in, (lzo_uint) in_len,
                                    out, (lzo_uint*) &new_len, wrkmem);
  }
  else if (method == M_LZO1X_999){
    err = lzo1x_999_compress_level(in, (lzo_uint)in_len,
                                         out, (lzo_uint*) &new_len, wrkmem,
                                         NULL, 0, 0, level);
  }
#endif
  else{
    PyMem_Free(wrkmem);
    PyMem_Free(out);
    PyErr_SetString(LzoError, "Compression method not supported");
    return NULL;
  }

  result = PyBytes_FromStringAndSize(out, new_len);
  if (result == NULL){
    return PyErr_NoMemory();
  }

  PyMem_Free(wrkmem);
  PyMem_Free(out);
  if (err != LZO_E_OK || new_len > out_len)
  {
    /* this should NEVER happen */
    Py_DECREF(result);
    PyErr_Format(LzoError, "Error %i while compressing data", err);
    return NULL;
  }

  return result;

}

static PyObject *
decompress_block(PyObject *dummy, PyObject *args)
{
  PyObject *result;

  lzo_bytep out;
  lzo_bytep in;

  Py_ssize_t in_len;
  Py_ssize_t dst_len;
  Py_ssize_t len;

  int err;
  UNUSED(dummy);
  
  if (!PyArg_ParseTuple(args, "s#n", &in, &in_len, &dst_len))
    return NULL;

  result = PyBytes_FromStringAndSize(NULL, dst_len);

  if (result == NULL) {
    return PyErr_NoMemory();
  }

  out = (lzo_bytep) PyBytes_AS_STRING(result);

  len = dst_len;
  err = lzo1x_decompress_safe(in, (lzo_uint)in_len, out, (lzo_uint*)&len, NULL);

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
  lzo_uint32 value = 1;
  const lzo_bytep in;
  Py_ssize_t len;

  lzo_uint32 new;

  if (!PyArg_ParseTuple(args, "s#|I", &in, &len, &value))
    return NULL;

  if(len>0){
    new = lzo_adler32(value, in, len);
    return Py_BuildValue("I", new);
  }
  else{
    return Py_BuildValue("I", value);
  }
}

#ifdef USE_LIBLZO
static PyObject *
py_lzo_crc32(PyObject *dummy, PyObject *args)
{
  lzo_uint32 value;
  const lzo_bytep in;
  Py_ssize_t len;

  lzo_uint32 new;

  if (!PyArg_ParseTuple(args, "Is#", &value, &in, &len))
    return NULL;
  
  if(len>0){
    new = lzo_crc32(value, in, len);
    return Py_BuildValue("I", new);
  }
  else{
    return Py_BuildValue("I", value);
  }
}
#endif

/***********************************************************************
// main
************************************************************************/

static /* const */ PyMethodDef methods[] =
{
    {"compress_block", (PyCFunction)compress_block, METH_VARARGS, compress__doc__},
    {"decompress_block", (PyCFunction)decompress_block, METH_VARARGS, decompress__doc__},
    {"lzo_adler32", (PyCFunction)py_lzo_adler32, METH_VARARGS, lzo_adler32__doc__},
#ifdef USE_LIBLZO
    {"lzo_crc32", (PyCFunction)py_lzo_crc32, METH_VARARGS, decompress__doc__},
#endif
    {NULL, NULL, 0, NULL}
};


static /* const */ char module_documentation[]=
"This is a python library deals with lzo files compressed with lzop.\n\n"

;

static PyModuleDef moduleSpec = {
	PyModuleDef_HEAD_INIT,
	/*.m_name=*/"_lzo",
	/*.m_doc=*/module_documentation,
	/*.m_size=*/-1,
	/*.m_methods=*/methods,
	/*.m_reload=*/NULL,
	/*.m_traverse=*/NULL,
	/*.m_clear=*/NULL,
	/*.m_free=*/NULL,
};

#ifdef _MSC_VER
_declspec(dllexport)
#endif
PyMODINIT_FUNC PyInit__lzo() {
    if (lzo_init() != LZO_E_OK)
    {
        return NULL;
    }
	PyObject *m = PyModule_Create(&moduleSpec);
	PyObject_SetAttrString(m, "__author__", PyUnicode_FromString("<iridiummx@gmail.com>"));
	PyObject_SetAttrString(m, "LZO_VERSION", PyLong_FromLong(LZO_VERSION));
	PyObject_SetAttrString(m, "LZO_VERSION_STRING", PyUnicode_FromString(LZO_VERSION_STRING));
	PyObject_SetAttrString(m, "LZO_VERSION_DATE", PyUnicode_FromString(LZO_VERSION_DATE));
	PyObject_SetAttrString(m, "error", (PyObject*) PyErr_NewException("_lzo.error", NULL, NULL));
	return m;
 }


/*
vi:ts=4:et
*/
