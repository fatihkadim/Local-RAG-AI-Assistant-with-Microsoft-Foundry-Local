import asyncio
from foundry_local_sdk import Configuration, FoundryLocalManager


async def main():
    config = Configuration(app_name="app-name")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    models = manager.catalog.list_models()

    with open("models.txt", "w", encoding="utf-8") as file:
        for model in models:
            file.write((model.id if hasattr(model, "id") else str(model)) + "\n")

if __name__ == "__main__":
    asyncio.run(main())