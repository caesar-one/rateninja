import multiprocessing
import time
from datetime import datetime, timedelta
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Callable

# copied from https://github.com/vcdi/ratemate/blob/master/ratemate/ratelim.py
class RateLimit:
    def __init__(self, max_count=1, per=1, greedy=False):
        self.greedy = greedy

        # if self.greedy:
        self._t_batch_start = multiprocessing.Value("d")
        self._batch_count = multiprocessing.Value("I")
        self._batch_count.value = 0

        # (utc) time of previous call, stored as unix timestamp (float)
        self._t_last_call = multiprocessing.Value("d")

        # number of calls
        self._count = multiprocessing.Value("I")
        self._count.value = 0

        # minimum required interval between calls
        self.max_count = max_count
        self.per = per
        self.per_timedelta = timedelta(seconds=self.per)

        # no more than max_rate calls should happen per second
        self.max_rate = max_count / per

        # to stay at the required rate, there should be at least this interval between calls
        self.min_interval = per / max_count

        self.min_interval_timedelta = timedelta(seconds=self.min_interval)

    def sleep(self, secs):
        time.sleep(secs)

    @property
    def count(self):
        return self._count.value

    @count.setter
    def count(self, value):
        self._count.value = value

    @property
    def batch_count(self):
        return self._batch_count.value

    @batch_count.setter
    def batch_count(self, value):
        self._batch_count.value = value

    @property
    def dt_previous_call(self):
        prev_call_unix = self._t_last_call.value

        if prev_call_unix:
            return datetime.fromtimestamp(prev_call_unix)

    @dt_previous_call.setter
    def dt_previous_call(self, value):
        self._t_last_call.value = value

    def is_first_call(self):
        return self.count == 0

    def wait_until(self, dt_wait_until):
        wait_interval = dt_wait_until - datetime.utcnow()
        wait_secs = wait_interval.total_seconds()

        if wait_secs > 0:
            self.sleep(wait_secs)
            return wait_secs
        return 0.0

    @property
    def dt_batch_start(self):
        _dt_batch_start = self._t_batch_start.value

        if _dt_batch_start:
            return datetime.fromtimestamp(_dt_batch_start)

    @dt_batch_start.setter
    def dt_batch_start(self, value):
        self._t_batch_start.value = value

    def wait(self):
        with self._count.get_lock(), self._t_last_call.get_lock(), self._t_batch_start.get_lock(), self._batch_count.get_lock():

            dt_previous_call = self.dt_previous_call

            wait_secs = 0.0

            if not self.is_first_call():
                if self.greedy:
                    self.batch_count += 1

                    if self.batch_count >= self.max_count:
                        self.batch_count = 0

                        dt_wait_until = self.dt_batch_start + self.per_timedelta
                        wait_secs = self.wait_until(dt_wait_until)
                else:
                    dt_wait_until = dt_previous_call + self.min_interval_timedelta
                    wait_secs = self.wait_until(dt_wait_until)

            self.count += 1

            now_timestamp = datetime.utcnow().timestamp()

            self.dt_previous_call = now_timestamp

            if self.greedy and self.batch_count:
                self.dt_batch_start = now_timestamp

            return wait_secs
        
class RateNinja:
    '''
    This class is used to call an API with a rate limit, using multithreading.
    '''
    def __init__(self, max_call_count=1, per_seconds=1, greedy=False, progress_bar=True, max_retries=5, max_workers=1, _disable_wait=False):
        '''
        max_count: maximum number of calls per per_seconds
        per_seconds: number of seconds per max_count
        greedy: The default (aka non-greedy aka patient) rate limiting mode spaces out calls evenly.
            For instance, max_count=10 and per=60 will result in one call every 6 seconds. You may instead 
            wish for calls to happen as fast as possible, only slowing down if the limit would be exceeded.
        progress_bar: whether to show a progress bar
        max_retries: maximum number of retries if an errors occur
        num_workers: number of workers that can perform calls
        _disable_wait: this disables the waiting before creating the task, so it does NOT respect the
            rate limits. Note that the .wait() must be used manually inside the function: use get_rate_limit_obj()
            to obtain the RateLimit object, and call its .wait() method inside your function every time you
            want to respect rate limits.
        '''
        self.rate_limit = RateLimit(max_count=max_call_count, per=per_seconds, greedy=greedy)
        self.progress_bar = progress_bar
        self.max_retries = max_retries
        self.max_workers = max_workers
        self._disable_wait = _disable_wait

    def get_rate_limit_obj(self):
        '''Returns: 
            RateLimit: the RateLimit object used to respect the rate limit. You can call its .wait() method
            inside your function every time you want to respect rate limits.'''
        return self.rate_limit
    
    def _call_aux(self, fct: Callable, func_args: List[Tuple] = None, func_kwargs: List[Dict] = None):
        '''
        for each tuple of arguments in func_args or each dictionary of keyword arguments in func_kwargs, call fct
        in a multithreaded way (different calls to fct are executed in parallel), respecting the rate limit.
        Useful for calling an API that has rate limits.

        Args:
            fct: the function to call
            func_args: a list of tuples of arguments to pass to fct
            func_kwargs: a list of dictionaries of keyword arguments to pass to fct

        Returns:
            Tuple[List[Union[Any, None]], List[Union[None, Any]]]: the first element of the tuple is a list having 
            the same length of func_args or func_kwargs, with the function's output if the call was successful, 
            None otherwise. The second element has the same structure as the first one, and contains None values if
            he call was successfull, the exception object raised by the function otherwise.
        '''
        # check params
        assert func_args is not None or func_kwargs is not None, "func_args or func_kwargs must be provided"
        if func_args is None:
            func_args = [()] * len(func_kwargs)
        if func_kwargs is None:
            func_kwargs = [{}] * len(func_args)

        total_length = len(func_args)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {}
            for idx, (_func_args, _func_kwargs) in tqdm(enumerate(zip(func_args, func_kwargs)), total=total_length, disable=not self.progress_bar, desc='API calls'):
                if not self._disable_wait:
                    self.rate_limit.wait()  # wait before creating the task
                future = executor.submit(fct, *_func_args, **_func_kwargs)
                future_to_idx[future] = idx

            results = [None for _ in range(total_length)]
            results_with_errors = [None for _ in range(total_length)]
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    data = future.result()
                    results[idx] = data
                except Exception as exc:
                    results_with_errors[idx] = exc
                else:
                    results[idx] = data
        return results, results_with_errors
    
    def __call__(self, fct: Callable, func_args: List[Tuple] = None, func_kwargs: List[Dict] = None):
        '''
        for each tuple of arguments in func_args or each dictionary of keyword arguments in func_kwargs, call fct
        in a multithreaded way (different calls to fct are executed in parallel), respecting the rate limit.
        Useful for calling an API that has rate limits.

        Args:
            fct: the function to call
            func_args: a list of tuples of arguments to pass to fct
            func_kwargs: a list of dictionaries of keyword arguments to pass to fct

        Returns:
            Tuple[List[Union[Any, None]], List[Union[None, Any]]]: the first element of the tuple is a list having 
            the same length of func_args or func_kwargs, with the function's output if the call was successful, 
            None otherwise. The second element has the same structure as the first one, and contains None values if
            he call was successfull, the exception object raised by the function otherwise.
        '''
        # check params
        assert func_args is not None or func_kwargs is not None, "func_args or func_kwargs must be provided"
        if func_args is None:
            func_args = [()] * len(func_kwargs)
        if func_kwargs is None:
            func_kwargs = [{}] * len(func_args)

        total_length = len(func_args)

        results, results_with_errors = self._call_aux(fct, func_args, func_kwargs)
        # retry errors
        for attempt_idx in range(1, self.max_retries + 1):
            if all([result is None for result in results_with_errors]):
                break
            print(f"Retrying {sum([result is not None for result in results_with_errors])} / {total_length} calls that failed, attempt {attempt_idx} / {self.max_retries} ...")
            retry_func_args = []
            retry_func_kwargs = []
            retry_mapping = []
            for idx, result_with_error in enumerate(results_with_errors):
                if result_with_error is not None:
                    retry_func_args.append(func_args[idx])
                    retry_func_kwargs.append(func_kwargs[idx])
                    retry_mapping.append(idx)
            retry_results, retry_results_with_errors = self._call_aux(fct, retry_func_args, retry_func_kwargs)
            for idx, result_with_error in enumerate(retry_results_with_errors):
                if result_with_error is not None:
                    results_with_errors[retry_mapping[idx]] = result_with_error
                else:
                    results[retry_mapping[idx]] = retry_results[idx]
                    results_with_errors[retry_mapping[idx]] = None
        return results, results_with_errors
    
# TESTS
if __name__ == "__main__":
    # test async call
    import random
    def fct(a, b):
        rnd = random.random()
        #print("rnd:", rnd)
        time.sleep(random.random())
        if rnd < 0.5:
            raise Exception("error")
        print(a, "+", b)
        return a + b
    async_call = AsyncCallAPIWithRateLimit(max_count=10, per_seconds=1, greedy=True, progress_bar=True, max_retries=10, max_workers=10)
    results, results_with_errors = async_call(fct, func_args=[(i, i) for i in range(100)])
    print(results)
    print(results_with_errors)
    assert results == [i + i for i in range(100)]
    assert results_with_errors.count(None) == 100

    # we now repeat the same test ensuring the rate limit is respected
    