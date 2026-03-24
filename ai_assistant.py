#!/bin/python

from vllm import LLM, SamplingParams

model = "mistralai/Devstral-Small-2-24B-Instruct-2512"
model = "mistralai/Mistral-7B-Instruct-v0.3"

prompts = [
    "Hello, my name is",
    #    "The president of the United States is",
    #    "The capital of France is",
    #   "The future of AI is",
]

sampling_params = SamplingParams(temperature=0.8, top_p=0.95)

llm = LLM(
    model=model,
    gpu_memory_utilization=0.3,
    swap_space=4,
    max_model_len=1024,
)

outputs = llm.generate(prompts, sampling_params)

for output in outputs:
    prompt = output.prompt
    generated_text = output.outputs[0].text
    print(f"Prompt: {prompt!r}, Generated text: {generated_text!r}")
