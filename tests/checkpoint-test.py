import io
import os
import shutil
import sys
import unittest
import pandas as pd
import numpy as np

import datetime
from skutil.IO import checkpoint

RM = "Runned."


def R():
    print(RM, end="")


@checkpoint
def empty():
    R()
    return 0


@checkpoint
def adding(a, b):
    R()
    return a+b


@checkpoint
def adding_with_default(a, b=3):
    R()
    return a+b


@checkpoint(ignore=["a"])
def adding_with_ignore(a, b=3):
    R()
    return a+b


@checkpoint
def return_input(val):
    R()
    return val


@checkpoint
def always_return_1(*args, **kwargs):
    R()
    return 1


class Foo(object):
    def __init__(self):
        self.a = 1

    @checkpoint
    def no_args(self):
        R()
        return self.a

    @checkpoint
    def with_args(self, b):
        R()
        return self.a + b

    @classmethod
    @checkpoint
    def class_method(cls, a):
        R()
        return a


class CheckpointTest(unittest.TestCase):
    arr1 = np.array([
        [1],
        [2]
    ])

    arr2 = np.array([
        [1, 1],
        [2, 2]
    ])

    df1 = pd.DataFrame({
        "a": [1],
        "b": [2]
    })

    df2 = pd.DataFrame({
        "a": [1],
        "b": [2.1]
    })

    s1 = pd.Series([1, 2, 3, 4])

    def setUp(self):
        self.M = io.StringIO()
        sys.stdout = self.M

    def clear(self):
        self.M.truncate(0)
        self.M.seek(0)

    def runned(self):
        self.assertEqual(self.M.getvalue(), RM)
        self.clear()

    def not_runned(self):
        self.assertEqual(self.M.getvalue(), "")
        self.clear()

    def tearDown(self):
        sys.stdout = sys.__stdout__
        dir_name = ".skutil-checkpoint"
        sub_dir_name = os.path.join("tests", dir_name)
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)

        if os.path.exists(sub_dir_name):
            shutil.rmtree(sub_dir_name)

    def test_empty(self):
        self.assertEqual(empty(), 0)
        self.runned()

        self.assertEqual(empty(), 0)
        self.not_runned()

    def test_adding(self):
        self.assertEqual(adding(2, 3), 2+3)
        self.runned()

        self.assertEqual(adding(3, 3), 3+3)
        self.runned()

        self.assertEqual(adding(2, 3), 2+3)
        self.not_runned()

        self.assertEqual(adding(2.0, 3.0), 2.0+3.0)
        self.runned()

    def test_adding_with_default(self):
        self.assertEqual(adding_with_default(2, 3), 2+3)
        self.runned()

        self.assertEqual(adding_with_default(3), 3+3)
        self.runned()

        self.assertEqual(adding_with_default(2), 2+3)
        self.not_runned()

        self.assertEqual(adding_with_default(2, 3), 2+3)
        self.not_runned()

    def test_ignore(self):
        self.assertEqual(adding_with_ignore(2, 3), 2+3)
        self.runned()

        self.assertEqual(adding_with_ignore(3, 3), 2+3)
        self.not_runned()

        self.assertEqual(adding_with_ignore(3, 4), 3+4)
        self.runned()

        self.assertEqual(adding_with_ignore(123), 2+3)
        self.not_runned()

    def test_return_input(self):

        self.assertTrue((return_input(self.df1) == self.df1).all().all())
        self.runned()

        self.assertTrue((return_input(self.df1) == self.df1).all().all())
        self.not_runned()

        self.assertTrue((return_input(self.df2) == self.df2).all().all())
        self.runned()

        self.assertTrue((return_input(self.df2) == self.df2).all().all())
        self.not_runned()

    def test_return_input(self):

        self.assertTrue((return_input(self.arr1) == self.arr1).all())
        self.runned()

        self.assertTrue((return_input(self.arr1) == self.arr1).all())
        self.not_runned()

        self.assertTrue((return_input(self.arr2) == self.arr2).all())
        self.runned()

        self.assertTrue((return_input(self.arr2) == self.arr2).all())
        self.not_runned()

        self.assertTrue((return_input(self.arr2.T) == self.arr2.T).all())
        self.runned()

        self.assertTrue((return_input(self.arr2.T) == self.arr2.T).all())
        self.not_runned()

    def test_method(self):
        f = Foo()
        self.assertEqual(f.no_args(), f.a)
        self.runned()

        self.assertEqual(f.no_args(), f.a)
        self.not_runned()

        self.assertEqual(f.with_args(3), f.a+3)
        self.runned()

        self.assertEqual(f.with_args(3), f.a+3)
        self.not_runned()

        f.a = 2
        self.assertEqual(f.no_args(), f.a)
        self.runned()

        self.assertEqual(f.with_args(3), f.a+3)
        self.runned()

    def test_class_method(self):
        self.assertEqual(Foo.class_method(1), 1)
        self.runned()

        self.assertEqual(Foo.class_method(1), 1)
        self.not_runned()

        self.assertEqual(Foo.class_method(2.5), 2.5)
        self.runned()

        self.assertEqual(Foo.class_method(2.5), 2.5)
        self.not_runned()

    def test_class_with_df(self):
        f = Foo()

        f.a = self.df1
        self.assertTrue((f.no_args() == f.a).all().all())
        self.runned()

        self.assertTrue((f.no_args() == f.a).all().all())
        self.not_runned()

        f.a = self.df2

        self.assertTrue((f.no_args() == f.a).all().all())
        self.runned()

        self.assertTrue((f.no_args() == f.a).all().all())
        self.not_runned()

        f.a = self.s1

        self.assertTrue((f.no_args() == f.a).all())
        self.runned()

        self.assertTrue((f.no_args() == f.a).all())
        self.not_runned()

        f.a = self.arr1

        self.assertTrue((f.no_args() == f.a).all())
        self.runned()

        self.assertTrue((f.no_args() == f.a).all())
        self.not_runned()

    def test_overwrite(self):
        self.assertEqual(adding_with_default(3, 3), 3+3)
        self.runned()

        self.assertEqual(adding_with_default(3, 3, __overwrite__=True), 3+3)
        self.runned()

        self.assertEqual(adding_with_default(3), 3+3)
        self.not_runned()

        with self.assertRaises(TypeError):
            adding_with_default(3, __overwrite__=1)

    def test_class_or_func_as_param(self):
        self.assertIs(always_return_1(empty), 1)
        self.runned()

        self.assertIs(always_return_1(empty), 1)
        self.not_runned()

        self.assertIs(always_return_1(Foo), 1)
        self.runned()

        self.assertIs(always_return_1(Foo), 1)
        self.not_runned()

    def test_kwargs(self):
        self.assertEqual(adding_with_default(a=3, b=5), 3+5)
        self.runned()

        self.assertEqual(adding_with_default(a=3, b=5), 3+5)
        self.not_runned()

        self.assertEqual(adding_with_default(a=3), 3+3)
        self.runned()

        self.assertEqual(adding_with_default(a=3), 3+3)
        self.not_runned()

    def test_time(self):
        big = np.random.rand(500000, 100)
        start = datetime.datetime.now()
        return_input(big)
        stop = datetime.datetime.now()
        self.runned()
        self.assertLessEqual((stop-start).seconds, 10)

        start = datetime.datetime.now()
        return_input(big)
        stop = datetime.datetime.now()
        self.not_runned()
        self.assertLessEqual((stop-start).seconds, 10)

        big = pd.DataFrame(big)
        start = datetime.datetime.now()
        return_input(big)
        stop = datetime.datetime.now()
        self.runned()
        self.assertLessEqual((stop-start).seconds, 10)

        start = datetime.datetime.now()
        return_input(big)
        stop = datetime.datetime.now()
        self.not_runned()
        self.assertLessEqual((stop-start).seconds, 10)
