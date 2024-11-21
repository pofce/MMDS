# define bloom filter class
from bitarray import bitarray
import mmh3
import math


class BloomFilter:
    def __init__(self, expected_items, false_positive_rate):
        """
        Initialize the Bloom filter with a given expected number of items and false positive rate.
        """
        self.expected_items = expected_items
        self.false_positive_rate = false_positive_rate
        self.size = self._calculate_size()
        self.hash_count = self._calculate_hash_count()
        self.bit_array = bitarray(self.size)
        self.bit_array.setall(0)

    def _calculate_size(self):
        """
        Calculate the size of the bit array (m) using the formula:
        m = -(n * log(p)) / (log(2)^2)
        """
        n = self.expected_items
        p = self.false_positive_rate
        return math.ceil(-(n * math.log(p)) / (math.log(2) ** 2))

    def _calculate_hash_count(self):
        """
        Calculate the optimal number of hash functions (k) using the formula:
        k = (m / n) * log(2)
        """
        m = self.size
        n = self.expected_items
        return math.ceil((m / n) * math.log(2))

    def add(self, item):
        """
        Add an item to the Bloom filter by hashing it with each hash function and setting the corresponding bits.
        """
        for i in range(self.hash_count):
            index = mmh3.hash(item, i) % self.size
            self.bit_array[index] = True

    def contains(self, item):
        """
        Check if an item is in the Bloom filter.
        Returns True if the item might be in the set, False if it is definitely not in the set.
        """
        for i in range(self.hash_count):
            index = mmh3.hash(item, i) % self.size
            if not self.bit_array[index]:
                return False
        return True

    def resize(self, additional_expected_items):
        """
        Resize the Bloom filter to accommodate additional expected items.
        This method recalculates the size and number of hash functions, and resizes the bit array.
        """

        self.expected_items += additional_expected_items
        new_size = self._calculate_size()
        new_hash_count = self._calculate_hash_count()

        if new_size > self.size:
            # Extend the bit array with additional bits set to 0
            additional_bits = new_size - self.size
            self.bit_array.extend([0] * additional_bits)
            self.size = new_size

        # Update the number of hash functions if it has changed
        if new_hash_count != self.hash_count:
            self.hash_count = new_hash_count

    def get_state(self):
        """
        Serialize the Bloom filter's state for distribution or saving.
        """
        return {
            "expected_items": self.expected_items,
            "false_positive_rate": self.false_positive_rate,
            "size": self.size,
            "hash_count": self.hash_count,
            "bit_array": self.bit_array.tobytes(),
        }

    @classmethod
    def from_state(cls, state):
        """
        Deserialize a Bloom filter from a serialized state.
        """
        obj = cls(
            expected_items=state["expected_items"],
            false_positive_rate=state["false_positive_rate"],
        )
        obj.size = state["size"]
        obj.hash_count = state["hash_count"]
        obj.bit_array = bitarray()
        obj.bit_array.frombytes(state["bit_array"])
        return obj
