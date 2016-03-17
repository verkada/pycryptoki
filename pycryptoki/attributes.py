"""
This module contains a wrapper around the key attributes and the template struct
generation to make it possible to create templates in python and easily
convert them into templates in C.
"""
import datetime
import logging
from collections import defaultdict
from ctypes import cast, c_void_p, create_string_buffer, c_bool, c_char_p, \
    c_ulong, pointer, POINTER, sizeof, c_char
from functools import wraps

from cryptoki import CK_ATTRIBUTE, CK_BBOOL, CK_ATTRIBUTE_TYPE, CK_ULONG, \
    CK_BYTE
from defines import CKA_USAGE_LIMIT, CKA_USAGE_COUNT, CKA_CLASS, CKA_TOKEN, \
    CKA_PRIVATE, CKA_LABEL, CKA_APPLICATION, CKA_CERTIFICATE_TYPE, \
    CKA_ISSUER, CKA_SERIAL_NUMBER, CKA_KEY_TYPE, CKA_SUBJECT, CKA_ID, CKA_SENSITIVE, \
    CKA_ENCRYPT, CKA_DECRYPT, CKA_WRAP, CKA_UNWRAP, CKA_SIGN, CKA_SIGN_RECOVER, \
    CKA_VERIFY, CKA_VERIFY_RECOVER, CKA_DERIVE, CKA_START_DATE, CKA_END_DATE, \
    CKA_MODULUS, CKA_MODULUS_BITS, CKA_PUBLIC_EXPONENT, CKA_PRIVATE_EXPONENT, \
    CKA_PRIME_1, CKA_PRIME_2, CKA_EXPONENT_1, CKA_EXPONENT_2, CKA_COEFFICIENT, \
    CKA_PRIME, CKA_SUBPRIME, CKA_BASE, CKA_PRIME_BITS, CKA_SUBPRIME_BITS, \
    CKA_VALUE_BITS, CKA_VALUE_LEN, CKA_LOCAL, \
    CKA_MODIFIABLE, CKA_EXTRACTABLE, CKA_ALWAYS_SENSITIVE, CKA_NEVER_EXTRACTABLE, \
    CKA_CCM_PRIVATE, CKA_FINGERPRINT_SHA1, CKA_FINGERPRINT_SHA256, CKA_OUID, CKA_UNWRAP_TEMPLATE, \
    CKA_DERIVE_TEMPLATE, \
    CKA_X9_31_GENERATED, CKA_VALUE
from pycryptoki.defines import CKA_EKM_UID, CKA_GENERIC_1, CKA_GENERIC_2, \
    CKA_GENERIC_3

LOG = logging.getLogger(__name__)


def get_byte_list_from_python_list(python_byte_list):
    """Helper method to create a C style byte list from a python
    style list of integers.

    :param python_byte_list: A list of integers to convert to a C style list of integers
    :returns: The pointer to the C representation of the python byte list

    """
    list_val = create_string_buffer("", len(python_byte_list))
    ptr = cast(pointer(list_val), c_void_p)
    for j in range(0, len(python_byte_list)):
        list_val[j] = chr(python_byte_list[j])
        return ptr


def ret_type(c_type):
    """
    Decorator to set a returned C Type so we can determine what type to use
    for an AutoCArray

    :param c_type: Default return-type of the transform function.
    """

    def func_wrapper(func):
        """
        Set the ctype on the function.

        :param func:
        :return:
        """
        func.ctype = c_type

        @wraps(func)
        def wrapped(*args, **kwargs):
            """
            Run the actual function.

            :param args:
            :param kwargs:
            :return:
            """
            return func(*args, **kwargs)

        return wrapped

    return func_wrapper


@ret_type(CK_ULONG)
def to_long(val, reverse=False):
    """Convert a integer/long value to a pValue, ulValueLen tuple

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`ctypes.c_ulong`, :class:`ctypes.c_ulong`
    size of long value)
    """
    if reverse:
        return long(cast(val.pValue, POINTER(c_ulong)).contents.value)
    if not isinstance(val, (int, long)):
        raise TypeError("Invalid conversion {} to CK_ULONG!".format(type(val)))
    long_val = CK_ULONG(val)
    return cast(pointer(long_val), c_void_p), CK_ULONG(sizeof(long_val))


@ret_type(CK_BBOOL)
def to_bool(val, reverse=False):
    """Convert a boolean-ish value to a pValue, ulValueLen tuple.

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`pycryptoki.cryptoki.CK_BBOOL`,
    :class:`ctypes.c_ulong` size of bool value)
    """
    if reverse:
        return bool(cast(val.pValue, POINTER(c_bool)).contents.value)

    if not isinstance(val, (int, bool)):
        raise TypeError("Invalid conversion {} to CK_BBOOL!".format(type(val)))
    # Convert to 0 | 1
    byte_val = CK_BBOOL(int(bool(val)))
    return cast(pointer(byte_val), c_void_p), CK_ULONG(sizeof(byte_val))


@ret_type(c_char)
def to_char_array(val, reverse=False):
    """Convert the given string or list of string values into a char array.

    This is slightly different than to_byte_array, which has different assumptions as
    to the format of the input.

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`pycryptoki.cryptoki.CK_CHAR` array,
    :class:`ctypes.c_ulong` size of array)
    """
    if reverse:
        return str(cast(val.pValue, c_char_p).value[0:val.usValueLen])

    if not isinstance(val, (str, list)):
        raise TypeError("Invalid conversion {} to CK_CHAR*!".format(type(val)))

    if isinstance(val, str):
        string_val = create_string_buffer(val)
    else:
        # TODO: Figure out what, if anything we want to do with a list.
        string_val = bytearray(val)
    return cast(pointer(string_val), c_void_p), CK_ULONG(sizeof(string_val))


@ret_type(c_char)
def to_ck_date(val, reverse=False):
    """Transform a date string, date dictionary, or date object into
    a PKCS11 readable form (YYYYMMDD)

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`pycryptoki.cryptoki.CK_CHAR` array,
    :class:`ctypes.c_ulong` size of array)
    """
    if reverse:
        return str(cast(val.pValue, c_char_p).value[0:val.usValueLen])

    if isinstance(val, str):
        if len(val) != 8:
            raise TypeError("Invalid date string passed! Should be of type YYYYMMDD")
        date_val = create_string_buffer(val)
    elif isinstance(val, dict):
        date_str = val['year'] + val['month'] + val['day']
        date_val = create_string_buffer(date_str)
    elif isinstance(val, datetime.date):
        date_val = create_string_buffer(val.strftime("%Y%m%d"))
    else:
        raise TypeError("Invalid conversion {} to CK_DATE!".format(type(val)))

    return cast(pointer(date_val), c_void_p), CK_ULONG(sizeof(date_val))


@ret_type(CK_BYTE)
def to_byte_array(val, reverse=False):
    """Converts an arbitrarily sized integer, list, or hex string
    into a byte array.

    It'll zero-pad the bit length so it's a multiple of 8, then convert
    the int to binary, split the binary string into sections of 8, then
    place each section into a slot in a :class:`ctypes.c_ubyte` array (converting to small
    int).

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`pycryptoki.cryptoki.CK_BYTE` array,
    :class:`ctypes.c_ulong` size of array)
    """
    if reverse:
        return cast(val.pValue, c_char_p).value[0:val.usValueLen]

    if isinstance(val, list):
        py_bytes = bytearray(val)
        byte_array = (CK_BYTE * len(py_bytes))(*py_bytes)
    elif isinstance(val, (int, long)):
        # Explicitly convert to a long. Python doesn't like X.bit_length() where X is an int
        # and not a variable assigned an int.
        width = long(val).bit_length()
        width += 8 - ((width % 8) or 8)

        fmt = "{:0%sb}" % width
        str_val = fmt.format(val)
        n = 8
        str_array = [str_val[i:i + n] for i in range(0, len(str_val), n)]
        byte_array = (CK_BYTE * len(str_array))(*[int(x, 2) for x in str_array])

    elif isinstance(val, str):
        # Can be Hex string ('01e4') or a bytestring (ex '\x8p\xb26\x12'G\xa3T\x84\x17\x89')
        try:
            # Would prefer to use bytearray.fromhex(), but a few testcases use ' ' * 80 or the like,
            # which is converted into a zero-length bytearray.
            hex_array = [val[i:i + 2] for i in range(0, len(val), 2)]
            byte_array = (CK_BYTE * len(val))(*[int(x, 16) for x in hex_array])
        except ValueError:
            # Assume a byte array?
            py_bytes = bytearray(val)
            byte_array = (CK_BYTE * len(py_bytes))(*py_bytes)
    else:
        raise TypeError("Invalid conversion {} to byte array!".format(type(val)))

    return cast(pointer(byte_array), c_void_p), CK_ULONG(sizeof(byte_array))


def to_sub_attributes(val, reverse=False):
    """
    Convert to another Attributes class & return the struct.

    :param val: Value to convert
    :param reverse: Whether to convert from C -> Python
    :return: (:class:`ctypes.c_void_p` ptr to :class:`pycryptoki.cryptoki.CK_ATTRIBUTE` array,
    :class:`ctypes.c_ulong` size of array)
    """
    if reverse:
        return c_struct_to_python(cast(val.pValue, POINTER(CK_ATTRIBUTE)))
    if not isinstance(val, dict):
        raise TypeError("Invalid conversion {} to Template!".format(type(val)))

    attrs = Attributes(**val).get_c_struct()

    return cast(pointer(attrs), c_void_p), CK_ULONG(len(attrs))


# Default any unset transform to :func:`to_byte_array`
KEY_TRANSFORMS = defaultdict(lambda: to_byte_array)

KEY_TRANSFORMS.update({
    # int, long
    CKA_CLASS: to_long,
    CKA_CERTIFICATE_TYPE: to_long,
    CKA_KEY_TYPE: to_long,
    CKA_VALUE_LEN: to_long,
    CKA_MODULUS_BITS: to_long,
    CKA_PRIME_BITS: to_long,
    CKA_SUBPRIME_BITS: to_long,
    CKA_VALUE_BITS: to_long,

    # int, bool
    CKA_TOKEN: to_bool,
    CKA_PRIVATE: to_bool,
    CKA_SENSITIVE: to_bool,
    CKA_ENCRYPT: to_bool,
    CKA_DECRYPT: to_bool,
    CKA_WRAP: to_bool,
    CKA_UNWRAP: to_bool,
    CKA_SIGN: to_bool,
    CKA_SIGN_RECOVER: to_bool,
    CKA_VERIFY: to_bool,
    CKA_VERIFY_RECOVER: to_bool,
    CKA_DERIVE: to_bool,
    CKA_CCM_PRIVATE: to_bool,
    CKA_LOCAL: to_bool,
    CKA_MODIFIABLE: to_bool,
    CKA_EXTRACTABLE: to_bool,
    CKA_ALWAYS_SENSITIVE: to_bool,
    CKA_NEVER_EXTRACTABLE: to_bool,
    CKA_X9_31_GENERATED: to_bool,

    # str, list(?)
    CKA_LABEL: to_char_array,
    CKA_APPLICATION: to_char_array,
    CKA_ISSUER: to_char_array,
    CKA_SUBJECT: to_char_array,
    CKA_ID: to_char_array,
    CKA_EKM_UID: to_char_array,
    CKA_GENERIC_1: to_char_array,
    CKA_GENERIC_2: to_char_array,
    CKA_GENERIC_3: to_char_array,

    # str, dict, datetime
    CKA_START_DATE: to_ck_date,
    CKA_END_DATE: to_ck_date,

    # Generic data.
    CKA_VALUE: to_byte_array,
    CKA_SERIAL_NUMBER: to_byte_array,
    CKA_MODULUS: to_byte_array,
    CKA_PUBLIC_EXPONENT: to_byte_array,
    CKA_PRIVATE_EXPONENT: to_byte_array,
    CKA_PRIME_1: to_byte_array,
    CKA_PRIME_2: to_byte_array,
    CKA_EXPONENT_1: to_byte_array,
    CKA_EXPONENT_2: to_byte_array,
    CKA_COEFFICIENT: to_byte_array,
    CKA_PRIME: to_byte_array,
    CKA_SUBPRIME: to_byte_array,
    CKA_BASE: to_byte_array,
    CKA_FINGERPRINT_SHA1: to_byte_array,
    CKA_FINGERPRINT_SHA256: to_byte_array,
    CKA_USAGE_COUNT: to_byte_array,
    CKA_USAGE_LIMIT: to_byte_array,
    CKA_OUID: to_byte_array,

    # Dict
    CKA_UNWRAP_TEMPLATE: to_sub_attributes,
    CKA_DERIVE_TEMPLATE: to_sub_attributes,
})


class Attributes(dict):
    """
    Python container for handling PKCS11 Attributes.

    Provides :func:`get_c_struct`, that would returns a list of C Structs, each with
    the following structure::

        class CK_ATTRIBUTE(Structure):
            '''
            Defines type, value and length of an attribute:

            c_ulong type;
            c_void_p pValue;
            c_ulong ulValueLen;
            '''
            pass


    This list of structs can be used with :func:`~pycryptoki.cryptoki.C_GetAttributeValue` to get
    the length of the value that will be placed
    in ``pValue`` (will be set to ``ulValueLen``), or if you already know the
    length required you can 'blank fill' ``pValue`` for direct use.

    You can also provide new transformations in the form of a dictionary that will be preferred
    to the :const:`~pycryptoki.attributes.KEY_TRANSFORMS` dictionary. This is passed in only as a
    keyword argument::

        transform = {1L: lambda x: return x**2}`
        attrs = Attributes({...}, new_transforms=transform)
        # attrs.get_c_struct will use the lambda expression in the transform dictionary
        # for key 1L

    """

    def __init__(self, *args, **kwargs):
        if 'new_transforms' in kwargs:
            self.new_transforms = kwargs.pop('new_transforms')
        else:
            self.new_transforms = {}
        super(Attributes, self).__init__(*args, **kwargs)

    def get_c_struct(self):
        """
        Build an array of :class:`~pycryptoki.cryptoki.CK_ATTRIBUTE` Structs & return it.

        :return: :class:`~pycryptoki.cryptoki.CK_ATTRIBUTE` array
        """
        ret_struct = (CK_ATTRIBUTE * len(self.keys()))()

        for index, key in enumerate(self.iterkeys()):
            value = self[key]
            if value is None:
                # Create an empty CK_ATTRIBUTE struct so it can be overwritten with length
                # data by the C_GetAttributeValue call.
                blank_attr = CK_ATTRIBUTE(CK_ATTRIBUTE_TYPE(key), None, CK_ULONG(0))
                ret_struct[index] = blank_attr
            elif key in self.new_transforms:
                p_value, ul_length = self.new_transforms[key](value)
                ret_struct[index] = CK_ATTRIBUTE(CK_ATTRIBUTE_TYPE(key),
                                                 p_value,
                                                 ul_length)
            else:
                if key not in KEY_TRANSFORMS:
                    LOG.warning("Using default `to_byte_array` transformation for key %s "
                                "and data %s", key, value)
                p_value, ul_length = KEY_TRANSFORMS[key](value)
                ret_struct[index] = CK_ATTRIBUTE(CK_ATTRIBUTE_TYPE(key),
                                                 p_value,
                                                 ul_length)
        return ret_struct

    @staticmethod
    def from_c_struct(c_struct):
        """
        Build out a dictionary from a c_struct.

        :param c_struct: Pointer to an array of :class:`~pycryptoki.cryptoki.CK_ATTRIBUTE` structs
        :return: dict
        """
        return c_struct_to_python(c_struct)


def c_struct_to_python(c_struct):
    """Converts a C struct to a python dictionary.

    :param c_struct: The c struct to convert into a dictionary in python
    :returns: Returns a python dictionary which represents the C struct passed in
    """
    py_data = {}
    for i in range(0, len(c_struct)):
        obj_type = c_struct[i].type
        if c_struct[i].pValue is None:
            py_data[obj_type] = None
        else:
            py_data[obj_type] = KEY_TRANSFORMS[obj_type](c_struct[i], reverse=True)

    return py_data


def convert_c_ubyte_array_to_string(byte_array):
    """Converts a ctypes unsigned byte array into a string.

    :param byte_array:
    """
    return "".join("%02x" % b for b in byte_array)
