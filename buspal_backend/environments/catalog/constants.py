# type: ignore
from google import genai

PROMPTS = {
  "MAIN": """
    You are a data extractor. You will receive a bulk of images for same product with different variations (i.e colors). Your task is to  extract a structured JSON data. Rely on both the visual processing and the textual captions. Only extract the fields you are 100% sure about its value. Never hallucinate, infer, or assume any field value.
    Think before extracting data and make sure that you process each image. Remember that text might be in between but it belongs to all the images. For each field in json, ask yourself if it can be visually detected, if it can turn it into a prompt and then apply it on the image to extract its value. For price check if price is added to the image, if not look at the textual content sent (if any).
  """
}

SCHEMAS = {
  "BUSINESS": genai.types.Schema(
      type = genai.types.Type.OBJECT,
      properties = {
          "sku": genai.types.Schema(
              type = genai.types.Type.STRING,
          ),
          "name": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Full product name",
          ),
          "tags": genai.types.Schema(
              type = genai.types.Type.ARRAY,
              items = genai.types.Schema(
                  type = genai.types.Type.STRING,
                  description = "Set of tags from caption if any.",
              ),
          ),
          "brand": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Brand or manufacturer of the shoe",
          ),
          "model": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Model or series name",
          ),
          "price": genai.types.Schema(
              type = genai.types.Type.OBJECT,
              required = ["amount", "currency"],
              properties = {
                  "amount": genai.types.Schema(
                      type = genai.types.Type.NUMBER,
                  ),
                  "currency": genai.types.Schema(
                      type = genai.types.Type.STRING,
                  ),
                  "discount": genai.types.Schema(
                      type = genai.types.Type.OBJECT,
                      properties = {
                          "percentage": genai.types.Schema(
                              type = genai.types.Type.NUMBER,
                          ),
                          "final_price": genai.types.Schema(
                              type = genai.types.Type.NUMBER,
                          ),
                      },
                  ),
              },
          ),
          "sizes": genai.types.Schema(
              type = genai.types.Type.ARRAY,
              items = genai.types.Schema(
                  type = genai.types.Type.OBJECT,
                  required = ["eu_size", "in_stock"],
                  properties = {
                      "eu_size": genai.types.Schema(
                          type = genai.types.Type.STRING,
                      ),
                      "in_stock": genai.types.Schema(
                          type = genai.types.Type.BOOLEAN,
                      ),
                  },
              ),
          ),
          "colors": genai.types.Schema(
              type = genai.types.Type.ARRAY,
              items = genai.types.Schema(
                  type = genai.types.Type.OBJECT,
                  properties = {
                      "main_color": genai.types.Schema(
                          type = genai.types.Type.STRING,
                          description = "The first main color that covers most of the shoe. Generally what a client would ask for",
                      ),
                      "secondary_color": genai.types.Schema(
                          type = genai.types.Type.STRING,
                          description = "The secondary color.",
                      ),
                  },
              ),
          ),
          "gender": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Target gender",
              enum = ["Men", "Women", "Unisex", "Kids"],
          ),
          "barcode": genai.types.Schema(
              type = genai.types.Type.STRING,
          ),
          "category": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Type of shoe (e.g., sneakers, boots)",
          ),
          "material": genai.types.Schema(
              type = genai.types.Type.STRING,
          ),
          "description": genai.types.Schema(
              type = genai.types.Type.STRING,
              description = "Detailed description of the shoe",
          ),
          "availability": genai.types.Schema(
              type = genai.types.Type.STRING,
              enum = ["in_stock", "out_of_stock", "pre_order", "discontinued"],
          ),
      },
  )
}