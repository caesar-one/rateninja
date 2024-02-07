# RateNinja

RateNinja is a Python package designed to facilitate the execution of function calls or API requests at a controlled rate, utilizing multithreading to maintain efficiency while adhering to rate limits. This package is particularly useful for interacting with APIs that impose call frequency restrictions, allowing developers to maximize throughput without violating terms of service.

## Features

- **Rate Limiting**: Enforces call frequency limits to comply with API rate limits.
- **Greedy and Non-Greedy Modes**: Supports both evenly spaced calls and as-fast-as-possible call execution within rate limits.
- **Progress Bar**: Visual feedback for tracking the progress of batched calls.
- **Retries**: Automatic retry mechanism for failed calls.
- **Multithreading**: Utilizes Python's `concurrent.futures.ThreadPoolExecutor` for parallel execution of calls within rate limits.

## Installation

Install RateNinja using pip:
```bash
pip install rateninja
```

## Usage

To use RateNinja, you need to import the `RateNinja` class from the package and then instantiate it with your desired rate limiting parameters. You can then pass the function (or API call) you wish to execute along with the function's arguments or keyword arguments.

### Basic Example

```python
from rateninja import RateNinja

# Function to be called
def calculate(param1, param2, operator="sum"):
    if operator == "sum":
        return param1 + param2
    elif operator == "multiplication":
        return param1 * param2
    else:
        raise Exception("Unrecognized operator")

# Initialize RateNinja with rate limiting parameters
rate_ninja = RateNinja(max_call_count=10, per_seconds=60, greedy=False, progress_bar=True, max_retries=5, max_workers=5)

# Prepare arguments for the function calls
func_args = [
    (3, 3),
    (4, 4),
    (5, 5),
] # List of tuples, each tuple contains arguments for one function call

func_kwargs = [
    {"operator": "sum"},
    {"operator": "multiplication"},
    {"operator": "ninja"},
]

# Execute the calls
results, errors = rate_ninja(my_function, func_args=func_args, func_kwargs=func_kwargs)

print("Results:", results)
print("Errors:", errors)
```

Should print:

```text
Results: [6, 16, None]
Errors: [None, None, Exception("Unrecognized operator")]
```

## Parameters

- `max_call_count`: Maximum number of calls allowed per `per_seconds` period.
- `per_seconds`: Time frame in seconds for the `max_call_count` limit.
- `greedy`: If `True`, executes calls as fast as possible within the limit. If `False`, spaces out calls evenly (e.g. if `max_call_count=10` and `per_seconds=10`, it will execute one call per second).
- `progress_bar`: Enables a visual progress bar if `True`.
- `max_retries`: Number of retries for failed calls.
- `max_workers`: Number of worker threads for parallel execution.
- `_disable_wait`: Allows to disable the internal wait mechanism that is used to respect rate limits. Note: if this is `True`, you will have to handle rate limits by yourself. To do this, use the `.get_rate_limit_obj()` method to get the `RateLimit` object instance, and use its `.wait()` method inside your function everytime you need to wait to respect rate limits.

## Contributing

Contributions to RateNinja are welcome!

## License

RateNinja is distributed under the Apache 2.0 License. See the LICENSE file in the GitHub repository for more details.