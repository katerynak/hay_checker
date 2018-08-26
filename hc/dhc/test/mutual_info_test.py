import random
import unittest
import logging

import numpy as np
from sklearn.metrics import mutual_info_score, normalized_mutual_info_score
from sklearn.metrics.cluster import adjusted_mutual_info_score
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, count, sum, col
from pyspark.sql.types import StringType, StructField, StructType, IntegerType, FloatType
import pandas as pd

from ..metrics import mutual_info

replace_empty_with_null = udf(lambda x: None if x == "" else x, StringType())
replace_0_with_null = udf(lambda x: None if x == 0 else x, IntegerType())
replace_0dot_with_null = udf(lambda x: None if x == 0. else x, FloatType())
replace_every_string_with_null = udf(lambda x: None, StringType())
replace_every_int_with_null = udf(lambda x: None, IntegerType())
replace_every_float_with_null = udf(lambda x: None, FloatType())


class TestMutualInfo(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestMutualInfo, self).__init__(*args, **kwargs)

        self.spark = SparkSession.builder.master("local[2]").appName("mutual_info_test").getOrCreate()
        self.spark.sparkContext.setLogLevel("ERROR")
        self.spark.conf.set("spark.sql.crossJoin.enabled", "true")

    def pmi(self, df, x, y):
        z = mutual_info_score(df[x], df[y])
        return z
        # df['f_x'] = df.groupby(x)[x].transform('count')
        # df['f_y'] = df.groupby(y)[y].transform('count')
        # df['f_xy'] = df.groupby([x, y])[x].transform('count')
        # df['pmi'] = np.log2(len(df.index) * df['f_xy'] / (df['f_x'] * df['f_y']))
        # print(df)
        # return df["pmi"].values[0]

    def test_empty(self):
        data = pd.DataFrame()
        data["c1"] = []
        data["c2"] = []
        schema = [StructField("c1", IntegerType(), True), StructField("c2", StringType(), True)]
        df = self.spark.createDataFrame(data, StructType(schema))

        r1 = mutual_info(0, 1, df)[0]
        self.assertEqual(r1, 0.)

    def test_allnull(self):
        data = pd.DataFrame()
        data["c1"] = [" " for i in range(100)]
        data["c2"] = [1 for i in range(100)]
        df = self.spark.createDataFrame(data)
        df = df.withColumn("c1", replace_every_string_with_null(df["c1"]))
        df = df.withColumn("c2", replace_every_int_with_null(df["c2"]))

        pmi = self.pmi(data, "c1", "c2")
        r = mutual_info(0, 1, df)[0]
        self.assertEqual(r, pmi)
        r = mutual_info(1, 0, df)[0]
        self.assertEqual(r, pmi)

    def test_allequal(self):
        data = pd.DataFrame()
        data["c1"] = [chr(0) for _ in range(100)]
        data["c2"] = [1 for _ in range(100)]
        df = self.spark.createDataFrame(data)

        pmi = self.pmi(data, "c1", "c2")
        r = mutual_info(0, 1, df)[0]
        self.assertEqual(r, pmi)
        r = mutual_info(1, 0, df)[0]
        self.assertEqual(r, pmi)

    def test_halfnull_halfequal(self):
        data = pd.DataFrame()
        c1 = [chr(1) for _ in range(50)]
        c2 = [2 for _ in range(50)]
        c1.extend(["" for _ in range(50)])
        c2.extend([0 for _ in range(50)])
        data["c1"] = c1
        data["c2"] = c2
        df = self.spark.createDataFrame(data)
        df = df.withColumn("c1", replace_empty_with_null(df["c1"]))
        df = df.withColumn("c2", replace_0_with_null(df["c2"]))

        pmi = self.pmi(data, "c1", "c2")
        r = mutual_info(0, 1, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)
        r = mutual_info(1, 0, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)

    def test_halfhalf(self):
        data = pd.DataFrame()
        c1 = [chr(1) for _ in range(50)]
        c2 = [2 for _ in range(50)]
        c3 = [0.7 for _ in range(50)]
        c1.extend(["zz" for _ in range(50)])
        c2.extend([100 for _ in range(50)])
        c3.extend([32. for _ in range(50)])
        data["c1"] = c1
        data["c2"] = c2
        data["c3"] = c3
        df = self.spark.createDataFrame(data)

        pmi = self.pmi(data, "c1", "c2")
        r = mutual_info(0, 1, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)
        r = mutual_info(1, 0, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)

        pmi = self.pmi(data, "c1", "c3")
        r = mutual_info(0, 2, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)
        r = mutual_info(2, 0, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)

        pmi = self.pmi(data, "c2", "c3")
        r = mutual_info(1, 2, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)
        r = mutual_info(2, 1, df)[0]
        self.assertAlmostEqual(r, pmi, delta=0.000001)

    def test_halfhalf_shuffled(self):
        for _ in range(2):
            data = pd.DataFrame()
            c1 = [chr(1) for _ in range(50)]
            c2 = [2 for _ in range(50)]
            c3 = [0.7 for _ in range(50)]
            c1.extend(["zz" for _ in range(50)])
            c2.extend([100 for _ in range(50)])
            c3.extend([32. for _ in range(50)])
            random.shuffle(c1)
            random.shuffle(c2)
            random.shuffle(c3)
            data["c1"] = c1
            data["c2"] = c2
            data["c3"] = c3
            df = self.spark.createDataFrame(data)

            pmi = self.pmi(data, "c1", "c2")
            r = mutual_info(0, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(1, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c1", "c3")
            r = mutual_info(0, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c2", "c3")
            r = mutual_info(1, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

    def test_halfhalf_shuffled_withnull(self):
        for _ in range(2):
            data = pd.DataFrame()
            c1 = [chr(1) for _ in range(50)]
            c2 = [2 for _ in range(50)]
            c3 = [0.7 for _ in range(50)]
            c1.extend(["" for _ in range(50)])
            c2.extend([0 for _ in range(50)])
            c3.extend([0. for _ in range(50)])
            random.shuffle(c1)
            random.shuffle(c2)
            random.shuffle(c3)
            data["c1"] = c1
            data["c2"] = c2
            data["c3"] = c3
            df = self.spark.createDataFrame(data)
            df = df.withColumn("c1", replace_empty_with_null(df["c1"]))
            df = df.withColumn("c2", replace_0_with_null(df["c2"]))
            df = df.withColumn("c3", replace_0dot_with_null(df["c3"]))

            pmi = self.pmi(data, "c1", "c2")
            r = mutual_info(0, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(1, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c1", "c3")
            r = mutual_info(0, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c2", "c3")
            r = mutual_info(1, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

    def test_mixed_shuffled_with_null(self):
        for _ in range(2):
            data = pd.DataFrame()
            c1 = [chr(i) for i in range(50)]
            c2 = [i for i in range(1, 51)]
            c3 = [i / 0.7 for i in range(1, 51)]
            c1.extend(["" for _ in range(50)])
            c2.extend([0 for _ in range(50)])
            c3.extend([0. for _ in range(50)])
            random.shuffle(c1)
            random.shuffle(c2)
            random.shuffle(c3)
            data["c1"] = c1
            data["c2"] = c2
            data["c3"] = c3
            df = self.spark.createDataFrame(data)
            df = df.withColumn("c1", replace_empty_with_null(df["c1"]))
            df = df.withColumn("c2", replace_0_with_null(df["c2"]))
            df = df.withColumn("c3", replace_0dot_with_null(df["c3"]))

            pmi = self.pmi(data, "c1", "c2")
            r = mutual_info(0, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(1, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c1", "c3")
            r = mutual_info(0, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 0, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)

            pmi = self.pmi(data, "c2", "c3")
            r = mutual_info(1, 2, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
            r = mutual_info(2, 1, df)[0]
            self.assertAlmostEqual(r, pmi, delta=0.000001)
