import json

with open("evaluation_set_with_all_responses.json", "r") as f:
    data = json.load(f)

with open("policygpt_experiment.json", "w") as f:
    experiment_data = {
        "name": "PolicyGPT Experiment",
        "instructions": "Below is a AI-generated policy question, along with answers from two different AI models. Choose the answer you prefer.",
        "items": [],
        "category_descriptions": {
            "pinecone": "Response from the Pinecone Assistant API",
            "custom": "Response from the custom PolicyGPT model"
        }
    }

    for item in data:
        experiment_data["items"].append({
            "content": f"## Question\n[Policy #{item['policy_number']}]({item['policy_url']})\n\n{item['question']}",
            "options": [
                {"text": item["pinecone_response"], "category": "pinecone"},
                {"text": item["custom_response"], "category": "custom"}
                ]
        })

    json.dump(experiment_data, f, indent=4)
