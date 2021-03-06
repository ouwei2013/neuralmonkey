#!/usr/bin/env python3.5

from typing import Iterable, List
import os
import tempfile
import unittest

from neuralmonkey.dataset import Dataset, from_files, load, BatchingScheme
from neuralmonkey.readers.plain_text_reader import UtfPlainTextReader

DEFAULT_BATCHING_SCHEME = BatchingScheme(
    batch_size=3,
    batch_bucket_span=None,
    token_level_batching=False,
    bucketing_ignore_series=[])


class TestDataset(unittest.TestCase):

    def test_nonexistent_file(self):
        with self.assertRaises(FileNotFoundError):
            load(name="name",
                 series=["source"],
                 data=[(["some_nonexistent_file"], UtfPlainTextReader)],
                 buffer_size=5)

    def test_nonexistent_file_deprec(self):
        with self.assertRaises(FileNotFoundError):
            from_files(
                name="name",
                s_source=(["some_nonexistent_file"], UtfPlainTextReader),
                lazy=True)

    def test_lazy_dataset(self):
        i = 0  # iteration counter

        def reader(files: List[str]) -> Iterable[List[str]]:
            del files
            nonlocal i
            for i in range(10):  # pylint: disable=unused-variable
                yield ["foo"]

        dataset = load(
            name="data",
            series=["source", "source_prep"],
            data=[([], reader), (lambda x: x, "source")],
            buffer_size=5)

        series = dataset.get_series("source_prep")

        # Check that the reader is being iterated lazily
        for j, _ in enumerate(series):
            self.assertEqual(i, j)
        self.assertEqual(i, 9)

    def test_lazy_dataset_deprec(self):
        i = 0  # iteration counter

        def reader(files: List[str]) -> Iterable[List[str]]:
            del files
            nonlocal i
            for i in range(10):  # pylint: disable=unused-variable
                yield ["foo"]

        dataset = from_files(
            name="data",
            s_source=([], reader),
            preprocessors=[("source", "source_prep", lambda x: x)],
            lazy=True)

        series = dataset.get_series("source_prep")

        # Check that the reader is being iterated lazily
        for j, _ in enumerate(series):
            self.assertEqual(i, j)
        self.assertEqual(i, 9)

    def test_glob(self):
        filenames = sorted(["abc1", "abc2", "abcxx", "xyz"])
        contents = ["a", "b", "c", "d"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            for fname, text in zip(filenames, contents):
                with open(os.path.join(tmp_dir, fname), "w") as file:
                    print(text, file=file)

            dataset = load(
                name="dataset",
                series=["data"],
                data=[[os.path.join(tmp_dir, "abc?"),
                       os.path.join(tmp_dir, "xyz*")]])

            series_iterator = dataset.get_series("data")
            self.assertEqual(list(series_iterator), [["a"], ["b"], ["d"]])

    def test_glob_deprec(self):
        filenames = sorted(["abc1", "abc2", "abcxx", "xyz"])
        contents = ["a", "b", "c", "d"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            for fname, text in zip(filenames, contents):
                with open(os.path.join(tmp_dir, fname), "w") as file:
                    print(text, file=file)

            dataset = from_files(
                name="dataset",
                s_data=[os.path.join(tmp_dir, "abc?"),
                        os.path.join(tmp_dir, "xyz*")])

            series_iterator = dataset.get_series("data")
            self.assertEqual(list(series_iterator), [["a"], ["b"], ["d"]])

    def test_batching_eager_noshuffle(self):
        iterators = {
            "a": lambda: range(5),
            "b": lambda: range(10, 15)
        }

        dataset = Dataset(
            "dataset", iterators=iterators, shuffled=False)

        batches = []
        for epoch in range(2):
            epoch = []
            for batch in dataset.batches(DEFAULT_BATCHING_SCHEME):
                epoch.append({s: list(batch.get_series(s)) for s in iterators})

            batches.append(epoch)

        self.assertEqual(
            batches, [[{"a": [0, 1, 2], "b": [10, 11, 12]},
                       {"a": [3, 4], "b": [13, 14]}],
                      [{"a": [0, 1, 2], "b": [10, 11, 12]},
                       {"a": [3, 4], "b": [13, 14]}]])

    def test_batching_lazy_noshuffle(self):
        iterators = {
            "a": lambda: range(5),
            "b": lambda: range(10, 15)
        }

        dataset = Dataset(
            "dataset", iterators=iterators, shuffled=False, buffer_size=(3, 5))

        batches = []
        for epoch in range(2):
            epoch = []
            for batch in dataset.batches(DEFAULT_BATCHING_SCHEME):
                epoch.append({s: list(batch.get_series(s)) for s in iterators})

            batches.append(epoch)

        self.assertEqual(
            batches, [[{"a": [0, 1, 2], "b": [10, 11, 12]},
                       {"a": [3, 4], "b": [13, 14]}],
                      [{"a": [0, 1, 2], "b": [10, 11, 12]},
                       {"a": [3, 4], "b": [13, 14]}]])

    def test_batching_eager_shuffle(self):
        iterators = {
            "a": lambda: range(5),
            "b": lambda: range(5, 10)
        }

        dataset = Dataset("dataset", iterators=iterators, shuffled=True)

        batches = []
        for epoch in range(2):
            epoch = []
            for batch in dataset.batches(DEFAULT_BATCHING_SCHEME):
                epoch.append({s: list(batch.get_series(s)) for s in iterators})

            batches.append(epoch)

        epoch_data = []
        epoch_data.append(
            [c for batch in batches[0] for b in batch.values() for c in b])
        epoch_data.append(
            [c for batch in batches[1] for b in batch.values() for c in b])

        self.assertEqual(set(epoch_data[0]), set(range(10)))
        self.assertEqual(set(epoch_data[0]), set(epoch_data[1]))
        self.assertNotEqual(epoch_data[0], epoch_data[1])

    def test_batching_lazy_shuffle(self):
        iterators = {
            "a": lambda: range(5),
            "b": lambda: range(5, 10)
        }

        dataset = Dataset(
            "dataset", iterators=iterators, shuffled=True, buffer_size=(3, 5))

        batches = []
        for epoch in range(2):
            epoch = []
            for batch in dataset.batches(DEFAULT_BATCHING_SCHEME):
                epoch.append({s: list(batch.get_series(s)) for s in iterators})

            batches.append(epoch)

        epoch_data = []
        epoch_data.append(
            [c for batch in batches[0] for b in batch.values() for c in b])
        epoch_data.append(
            [c for batch in batches[1] for b in batch.values() for c in b])

        self.assertEqual(set(epoch_data[0]), set(range(10)))
        self.assertEqual(set(epoch_data[0]), set(epoch_data[1]))
        self.assertNotEqual(epoch_data[0], epoch_data[1])

    def test_bucketing(self):

        # testing dataset is 50 sequences of lengths 1 - 50
        iterators = {
            "sentences": lambda: (["word" for _ in range(l)]
                                  for l in range(1, 50))
        }

        dataset = Dataset("dataset", iterators=iterators, shuffled=False)

        # we use batch size 7 and bucket span 10
        scheme = BatchingScheme(7, 10, False, None, True)

        # we process the dataset in two epochs and save what did the batches
        # look like
        batches = []
        for batch in dataset.batches(scheme):
            batches.append(list(batch.get_series("sentences")))

        ref_batches = [
            [["word" for _ in range(l)] for l in range(1, 8)],
            [["word" for _ in range(l)] for l in range(10, 17)],
            [["word" for _ in range(l)] for l in range(20, 27)],
            [["word" for _ in range(l)] for l in range(30, 37)],
            [["word" for _ in range(l)] for l in range(40, 47)],
            [["word" for _ in range(l)] for l in range(8, 10)],
            [["word" for _ in range(l)] for l in range(17, 20)],
            [["word" for _ in range(l)] for l in range(27, 30)],
            [["word" for _ in range(l)] for l in range(37, 40)],
            [["word" for _ in range(l)] for l in range(47, 50)]]

        self.assertSequenceEqual(ref_batches, batches)

    def test_bucketing_no_leftovers(self):

        # testing dataset is 50 sequences of lengths 1 - 50
        iterators = {
            "sentences": lambda: (["word" for _ in range(l)]
                                  for l in range(1, 50))
        }

        dataset = Dataset("dataset", iterators=iterators, shuffled=False)

        # we use batch size 7 and bucket span 10
        scheme = BatchingScheme(7, 10, False, None, False)

        # we process the dataset in two epochs and save what did the batches
        # look like
        batches = []
        for batch in dataset.batches(scheme):
            batches.append(list(batch.get_series("sentences")))

        ref_batches = [
            [["word" for _ in range(l)] for l in range(1, 8)],
            [["word" for _ in range(l)] for l in range(10, 17)],
            [["word" for _ in range(l)] for l in range(20, 27)],
            [["word" for _ in range(l)] for l in range(30, 37)],
            [["word" for _ in range(l)] for l in range(40, 47)]]

        self.assertSequenceEqual(ref_batches, batches)

    def test_buckets_similar_size(self):
        # testing dataset is 3 x 6 sequences of lengths 0 - 5
        iterators = {
            "sentences": lambda: [["word" for _ in range(l)]
                                  for l in range(6)] * 3
        }

        dataset = Dataset("dataset", iterators=iterators, shuffled=True)

        # we use batch size 6 and bucket span 2
        scheme = BatchingScheme(6, 2, False, None)

        # we process the dataset in two epochs and save what did the batches
        # look like
        batches = []
        for batch in dataset.batches(scheme):
            batches.append(list(batch.get_series("sentences")))

        # this setup should divide the data to 3 batches
        self.assertEqual(len(batches), 3)

        for batch in batches:
            # each batch should contain 6 values
            self.assertEqual(len(batch), 6)

            lengths = set(len(b) for b in batch)

            # the values in the batch should have two lengths
            self.assertEqual(len(lengths), 2)

            # the lengths should differ by one
            self.assertEqual(max(lengths) - min(lengths), 1)


if __name__ == "__main__":
    unittest.main()
