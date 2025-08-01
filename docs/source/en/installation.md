# Installation Options

The `smolagents` library can be installed using pip. Here are the different installation methods and options available.

## Prerequisites
- Python 3.10 or newer
- pip

## Basic Installation

Install `smolagents` core library with:
```bash
pip install smolagents
```

## Installation with Extras

`smolagents` provides several optional dependencies (extras) that can be installed based on your needs.
You can install these extras using the following syntax:
```bash
pip install "smolagents[extra1,extra2]"
```

### Tools
These extras include various tools and integrations:
- **toolkit**: Install a default set of tools for common tasks.
  ```bash
  pip install "smolagents[toolkit]"
  ```
- **mcp**: Add support for the Model Context Protocol (MCP) to integrate with external tools and services.
  ```bash
  pip install "smolagents[mcp]"
  ```

### Model Integration
These extras enable integration with various AI models and frameworks:
- **openai**: Add support for OpenAI API models.
  ```bash
  pip install "smolagents[openai]"
  ```
- **transformers**: Enable Hugging Face Transformers models.
  ```bash
  pip install "smolagents[transformers]"
  ```
- **vllm**: Add VLLM support for efficient model inference.
  ```bash
  pip install "smolagents[vllm]"
  ```
- **mlx-lm**: Enable support for MLX-LM models.
  ```bash
  pip install "smolagents[mlx-lm]"
  ```
- **litellm**: Add LiteLLM support for lightweight model inference.
  ```bash
  pip install "smolagents[litellm]"
  ```
- **bedrock**: Enable support for AWS Bedrock models.
  ```bash
  pip install "smolagents[bedrock]"
  ```

### Multimodal Capabilities
Extras for handling different types of media and input:
- **vision**: Add support for image processing and computer vision tasks.
  ```bash
  pip install "smolagents[vision]"
  ```
- **audio**: Enable audio processing capabilities.
  ```bash
  pip install "smolagents[audio]"
  ```

### Remote Execution
Extras for executing code remotely:
- **docker**: Add support for executing code in Docker containers.
  ```bash
  pip install "smolagents[docker]"
  ```
- **e2b**: Enable E2B support for remote execution.
  ```bash
  pip install "smolagents[e2b]"
  ```
- **yepcode**: Enable YepCode support for cloud-based serverless execution with automatic package installation.
  ```bash
  pip install "smolagents[yepcode]"
  ```

### Telemetry and User Interface
Extras for telemetry, monitoring and user interface components:
- **telemetry**: Add support for monitoring and tracing.
  ```bash
  pip install "smolagents[telemetry]"
  ```
- **gradio**: Add support for interactive Gradio UI components.
  ```bash
  pip install "smolagents[gradio]"
  ```

### Complete Installation
To install all available extras, you can use:
```bash
pip install "smolagents[all]"
```

## Verifying Installation
After installation, you can verify that `smolagents` is installed correctly by running:
```python
import smolagents
print(smolagents.__version__)
```

## Next Steps
Once you have successfully installed `smolagents`, you can:
- Follow the [guided tour](./guided_tour) to learn the basics.
- Explore the [how-to guides](./examples/text_to_sql) for practical examples.
- Read the [conceptual guides](./conceptual_guides/intro_agents) for high-level explanations.
- Check out the [tutorials](./tutorials/building_good_agents) for in-depth tutorials on building agents.
- Explore the [API reference](./reference/index) for detailed information on classes and functions.
