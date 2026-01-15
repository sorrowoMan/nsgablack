# Function Bias Template

Template for function-style biases using `BiasModule`.

## File
- `bias/template_function_bias.py`

## What it contains
- `penalty_template`: returns a penalty dict
- `reward_template`: returns a reward dict
- `build_bias_module`: builds a `BiasModule`

## Usage
Import `build_bias_module()` and attach it to the solver:
```
solver.enable_bias = True
solver.bias_module = build_bias_module()
```
