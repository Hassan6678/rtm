# Function to recursively replace placeholders in both keys and values
def replace_placeholders(data, company, country):
    if isinstance(data, str):  # If the value is a string, perform the replacement
        return data.replace("{{ company }}", company).replace("{{ country }}", country)
    elif isinstance(data, dict):  # If it's a dictionary, recursively apply to its keys and values
        # Handle dynamic key replacement
        updated_dict = {}
        for key, value in data.items():
            # Replace company and country in the key itself
            new_key = key.replace("{{ company }}", company).replace("{{ country }}", country)
            updated_dict[new_key] = replace_placeholders(value, company, country)
        return updated_dict
    else:
        return data  # Return the data as is if it's neither a string nor a dictionary