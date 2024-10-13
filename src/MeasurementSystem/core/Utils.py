from __future__ import annotations

import queue
from typing import Any, Tuple


class OrderedPriorityQueue(queue.PriorityQueue):
    """
    A priority queue that preserves the order of elements with the same priority.

    :class:`OrderedPriorityQueue` extends the standard :class:`PriorityQueue` to ensure that elements with the same priority are
    retrieved in the order they were inserted. This is achieved by using a tuple as the priority,
    where the first element is the actual priority and the second element is a unique counter.


    :param name: The name of the queue.
    :type name: str

    :return: OrderedPriorityQueue object
    :rtype: OrderedPriorityQueue
    """

    def __init__(self, name):
        super().__init__()
        self.name = name
        self._sequence_number = 0

    def put(
        self,
        queue_element: Any,
        priority: float = 5,
        block: bool = True,
        timeout: float = None,
    ) -> None:
        """
        Put an element into the queue.

        This method puts an element into the queue with a given priority.
        The element is a tuple containing the priority, a sequence number and the queue element.
        The sequence number is used to ensure that elements with the same priority are processed
        in the order they were added to the queue.

        :param queue_element: The element to be added to the queue.
        :type queue_element: Any
        :param priority: The priority of the element. Elements with higher priority are processed first. Defaults to 5.
        :type priority: float
        :param block: If True, block until a free slot is available, otherwise raise the QueueFull exception. Defaults to True.
        :type block: bool
        :param timeout: The maximum time to wait for a free slot in the queue. If None, wait forever. Defaults to None.
        :type timeout: float
        :return: None
        :rtype: None
        """

        super().put(
            (priority, self._sequence_number, queue_element),
            block=block,
            timeout=timeout,
        )
        self._sequence_number += 1

    def get(self, block: bool = True, timeout: float = None) -> Tuple[Any, float]:
        """
        Get an element from the queue.

        This method gets an element from the queue.
        The element is a tuple containing the queue element and the priority.

        :param block: If True, block until an element is available, otherwise raise the QueueEmpty exception. Defaults to True.
        :type block: bool
        :param timeout: The maximum time to wait for an element. If None, wait forever. Defaults to None.
        :type timeout: float
        :return: Queue element and its priority.
        :rtype: Tuple[Any, float]
        """

        priority, sequence_number, queue_element = super().get(block=block, timeout=timeout)
        return queue_element, priority


# TEST
if __name__ == "__main__":
    q = OrderedPriorityQueue("test")

    # fill the queue
    for i in range(10):
        q.put(i)

    # read the queue
    while True:
        try:
            priority, queue_element = q.get(timeout=1)
            print(f"Priority: {priority}, QueueElement: {queue_element}")
        except queue.Empty:
            break

    print("done")
