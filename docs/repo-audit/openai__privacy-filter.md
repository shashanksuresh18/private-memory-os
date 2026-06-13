# openai/privacy-filter

Audit generated: 2026-05-27T23:58:06.407904+00:00
Local clone: `repos-audit\openai__privacy-filter`

## GitHub Metrics (Scrapling probe)


## Git Snapshot

- branch: `main`
- head:   `f7f00ca7fb869683eb732c010299d901457f19c3`
- last commit: 2026-04-22 12:55:02 -0700 f7f00ca Mihai (@OpenAI) Maruseac
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Mihai (@OpenAI) Maruseac <mihaimaruseac@openai.com>

## License

Apache License | Version 2.0, January 2004 | http://www.apache.org/licenses/

## Languages (by total bytes — top 10)

- `.py`: 316,202 bytes
- `.sh`: 30,792 bytes
- `.md`: 23,217 bytes
- `(noext)`: 11,683 bytes
- `.jsonl`: 4,957 bytes
- `.toml`: 485 bytes
- `.json`: 103 bytes

## Dependencies

### `pyproject_dependencies_sample`
- huggingface_hub
- numpy
- packaging
- torch
- safetensors
- tiktoken
### `pkg_name`
```
opf
```

## README — first 80 lines

```
# OpenAI Privacy Filter

OpenAI Privacy Filter is a bidirectional token-classification model for personally identifiable information (PII) detection and masking in text. It is intended for high-throughput data sanitization workflows where teams need a model that they can run on-premises that is fast, context-aware, and tunable.

OpenAI Privacy Filter is pretrained autoregressively to arrive at a checkpoint with similar architecture to gpt-oss, albeit of a smaller size.  We  then converted that checkpoint into a bidirectional token classifier over a privacy label taxonomy, and post-trained with a supervised classification loss. (For architecture details about gpt-oss, please see the gpt-oss model card.) Instead of generating text token-by-token, this model labels an input sequence in a single forward pass, then decodes coherent spans with a constrained Viterbi procedure. For each input token, the model predicts a probability distribution over the label taxonomy which consists of 8 output categories described below.

Highlights:

- Permissive Apache 2.0 license: ideal for experimentation, customization, and commercial deployment.
- Small size: Runs in a web browser or on a laptop – 1.5B parameters total and 50M active parameters.
- Fine-tunable: Adapt the model to specific data distributions through easy and data efficient finetuning.
- Long-context: 128,000-token context window enables processing long text with high throughput and no chunking.
- Runtime control: configure precision/recall tradeoffs and detected span lengths through preset operating points.

## This Repo

This repository contains the local code, CLI, and example assets used to run, evaluate, and finetune Privacy Filter checkpoints. It is meant for teams that want to inspect the implementation directly and operate the model in their own environment.

Repository resources: [License](LICENSE) and [Security Policy](SECURITY.md).

### How To Use

1. Install the package locally:

```bash
pip install -e .
```

After this, you will have a python script `opf` that can be run directly or via `python -m opf`. The script can be used in 3 separate ways, as described below.

2. Run one-shot redaction:

By default, `opf` looks for a model at the directory pointed to by the `OPF_CHECKPOINT` variable, or `~/.opf/privacy_filter`. If a model is not found in the `~/.opf/privacy_filter` location, it will be downloaded.

```bash
opf "Alice was born on 1990-01-02."
```

The code supports running both on GPU (by default) and CPU. To run on CPU, use `--device cpu` flag:

```bash
opf --device cpu "Alice was born on 1990-01-02."
```

To override the default checkpoint, pass `--checkpoint`:

```bash
opf --checkpoint /path/to/checkpoint_dir "Alice was born on 1990-01-02."
```

The redaction mode supports redacting an entire file at once

```bash
opf -f /path/to/file
```

The redaction can also be performed via pipes, to support complex one-liners:

```bash
cat /path/to/file | grep -e 'some_pattern' | opf
```

If no input is provided, `opf` will start in interactive mode. In this mode, for each input example, the CLI prints structured JSON output, using ANSI color-coded previews if the terminal supports them. These options can be controlled by flags.

Consult `opf redact --help` for more flags and information about the redaction mode.

3. Run eval on a labeled dataset:

```bash
opf eval examples/data/sample_eval_five_examples.jsonl
```

The sample eval fixtures under `examples/data/sample_eval_five_examples*.jsonl` are synthetic example data only and do not describe real people or real sensitive records. See `examples/data/README.md`.

Consult `opf eval --help` for more flags and information about the evaluation mode.

4. Finetune on your own labeled dataset:

```bash
opf train /path/to/train.jsonl --output-dir /path/to/finetuned_checkpoint
```
