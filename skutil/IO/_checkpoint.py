import os

import joblib
import re

from skutil.IO._check_util import (_get_applied_args,
                                   _get_hash_of_str,
                                   _get_identify_str_for_func,
                                   _get_file_info,
                                   _get_identify_str_for_cls_or_object,
                                   _get_identify_str_for_value,
                                   _check_handleable,
                                   _check_inline_handleable,
                                   )

from skutil.IO._exceptions import SkipWithBlock
import sys
import inspect
import logging
import glob


_save_dir = ".skutil-checkpoint"


def checkpoint(ignore=[]):
    if callable(ignore):
        param_is_callable = True
        func = ignore
        ignore = []
    elif isinstance(ignore, (list, tuple)):
        param_is_callable = False
    else:
        raise TypeError(f"Unsupported parameter type '{type(ignore)}'")

    def wrapper(func):
        def inner(*args, __overwrite__=False, **kwargs):
            if not os.path.exists(_save_dir):
                os.mkdir(_save_dir)

            if not isinstance(__overwrite__, bool):
                raise TypeError(
                    "'__overwrite__' parameter must be a boolean type")

            _check_handleable(func)
            file_info = _get_file_info(func)

            applied_args = _get_applied_args(func, args, kwargs)
            id_str = _get_identify_str_for_func(func, applied_args, ignore)
            hash_val = _get_hash_of_str(file_info + id_str)

            cache_path = os.path.join(_save_dir, f"{hash_val}.pkl")
            if os.path.exists(cache_path) and not __overwrite__:
                return joblib.load(cache_path)
            else:
                res = func(*args, **kwargs)
                joblib.dump(res, cache_path)
                return res
        return inner

    if param_is_callable:
        return wrapper(func)
    else:
        return wrapper


class InlineCheckpoint(object):
    def __init__(self, *, watch, produce, _id="default"):
        assert isinstance(watch, (list, tuple))
        assert isinstance(produce, (list, tuple))
        self.watch = watch
        self.produce = produce
        self._id = _id

        if not os.path.exists(_save_dir):
            os.mkdir(_save_dir)

        call_f = inspect.currentframe().f_back
        self.locals = call_f.f_locals
        self.globals = call_f.f_globals

        self.__check_watch_produce()

        status_str = self.__get_status_str()
        self.status_hash = _get_hash_of_str(status_str)

        logging.debug(f"status_str: {status_str}")

        self.skip = self.__checkpoint_exists()

    def __get_watch(self,i):
        assert isinstance(i, str)
        e = ValueError(f"{i} is not a valid identifier.")
        ref_list = i.split(".")
        if ref_list[0] not in self.locals:
            raise e
        curr = self.locals[ref_list[0]]
        for ref in ref_list[1:]:
            if not hasattr(curr, ref):
                raise e
            else:
                curr = getattr(curr, ref)
        return curr


    def __check_watch_produce(self):
        for i in self.watch:
            self.__get_watch(i)

        for i in self.produce:
            assert isinstance(i, str)
            e = ValueError(f"{i} is not a valid identifier.")
            pattern = "^[a-zA-Z_][a-zA-Z_0-9]*$"

            if "." in i:
                ref_list = i.split(".")
                if ref_list[0] not in self.locals:
                    raise e
                curr = self.locals[ref_list[0]]
                for ref in ref_list[1:-1]:
                    if not hasattr(curr, ref):
                        raise e
                    else:
                        curr = getattr(curr, ref)

                if not re.compile(pattern).match(ref_list[-1]):
                    raise e
            else:
                if not re.compile(pattern).match(i):
                    raise e

    def __get_status_str(self):
        watch_dict = {}

        for i in self.watch:
            value = self.__get_watch(i)
            _check_inline_handleable(value)
            if inspect.ismethod(value) or inspect.isfunction(value):
                watch_dict[i] = _get_identify_str_for_func(value)
            else:
                watch_dict[i] = _get_identify_str_for_value(value)

        watch_str = "-".join([f"{k}:{v}" for k,
                              v in watch_dict.items()])

        if "_ih" in self.globals and "In" in self.globals and "__file__" not in self.globals:
            file_name = "jupyter-notebook"
            source = "\n".join(self.globals["In"])
        elif "__file__" in self.globals:
            file_name = os.path.basename(self.globals["__file__"])
            with open(self.globals["__file__"], "r", encoding="utf-8") as f:
                source = f.read()
        else:
            logging.debug(self.globals)
            raise Exception(
                "Unknown error when detecting jupyter or .py environment.")

        sourcelines = source.split("\n")
        if self._id != "default":
            pattern = r'''(\s*)with .*?\(\s*watch\s*=\s*[\[\(]\s*['"]%s['"][\]\)]\s*,\s+produce\s*=\s*[\[\(]\s*['"]%s['"][\]\)]\s*,\s*_id\s*=\s*['"]%s['"]\).*?:''' % (
                '''['"]\s*,\s*['"]'''.join(self.watch), '''['"]\s*,\s*['"]'''.join(self.produce), self._id)
        else:
            pattern = r'''(\s*)with .*?\(\s*watch\s*=\s*[\[\(]\s*['"]%s['"][\]\)]\s*,\s+produce\s*=\s*[\[\(]\s*['"]%s['"][\]\)]\s*(?:,\s*_id\s*=\s*['"]%s['"])?\).*?:''' % (
                '''['"]\s*,\s*['"]'''.join(self.watch), '''['"]\s*,\s*['"]'''.join(self.produce), self._id)

        matcher = re.compile(pattern)

        start_line = None
        for lineno, line in enumerate(sourcelines):
            res = matcher.match(line)
            if res:
                start_line = lineno
                indent = res.group(1)

        if start_line is None:
            raise Exception(
                "Failed to check the content in the with-statement.")

        with_statement_lines = []
        for i in range(start_line+1, len(sourcelines)):
            line = sourcelines[i]
            pattern = indent+r"\s+\S+"
            matcher = re.compile(pattern)
            if matcher.match(line):
                with_statement_lines.append(line)
            else:
                break

        with_statement = ";".join([i.strip() for i in with_statement_lines])

        identify_str = f"{self._id}-{file_name}-{watch_str}-{with_statement}"
        return identify_str

    def __checkpoint_exists(self):
        for i in self.produce:
            if not os.path.exists(self.__cache_file_name(i)):
                return False
        return True

    def __enter__(self):
        if self.skip:
            sys.settrace(lambda *args, **keys: None)
            frame = sys._getframe(1)
            frame.f_trace = self._trace
        return self

    def _trace(self, frame, event, arg):
        raise SkipWithBlock()

    def __exit__(self, type, value, traceback):
        if self.skip:
            for i in self.produce:
                self.__retrieve(i)
        else:
            for i in self.produce:
                self.__save(i)

        if type is None:
            return
        if issubclass(type, SkipWithBlock):
            return True

    def __cache_file_name(self, i):
        return os.path.join(_save_dir, f"{self.status_hash}-{i}.pkl")

    def __retrieve(self, i):
        obj = joblib.load(self.__cache_file_name(i))

        if "." not in i:
            self.locals[i] = obj
        else:
            ref_list = i.split(".")
            curr = self.locals[ref_list[0]]
            for ref in ref_list[1:-1]:
                curr = getattr(curr, ref)

            setattr(curr, ref_list[-1], obj)

    def __save(self, i):
        if "." not in i:
            obj = self.locals[i]
        else:
            ref_list = i.split(".")
            curr = self.locals[ref_list[0]]
            for ref in ref_list[1:]:
                curr = getattr(curr, ref)
            obj = curr

        joblib.dump(obj, self.__cache_file_name(i))
