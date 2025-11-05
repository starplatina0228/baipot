
import csv
import json
from collections import defaultdict

def generate_ship_data_json():
    """
    Reads ship_info.csv and converts it into a JSON object
    structured by shipping company.
    """
    ship_data_by_company = defaultdict(list)
    
    try:
        with open('backend/ship_info.csv', mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                
                shipping_company = cleaned_row.get('선사')
                
                if shipping_company:
                    ship_name = cleaned_row.get('선명')
                    
                    # If ship name starts with the company name, remove the prefix
                    if ship_name and ship_name.startswith(shipping_company):
                        ship_name = ship_name[len(shipping_company):].strip()

                    ship_info = {
                        'call_sign': cleaned_row.get('호출부호'),
                        'ship_name': ship_name,  # Use the modified name
                        'gross_tonnage': int(cleaned_row.get('총톤수', 0)),
                        'LOA': int(cleaned_row.get('LOA', 0))
                    }
                    ship_data_by_company[shipping_company].append(ship_info)

        # Convert defaultdict to a regular dict and save to a JSON file
        output_path = 'frontend/src/data/ship_data.json' # Update path to point to frontend directory
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(dict(ship_data_by_company), jsonfile, indent=2, ensure_ascii=False)
        print(f"Successfully created {output_path}")

    except FileNotFoundError:
        print(json.dumps({"error": "ship_info.csv not found in backend directory."}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))

if __name__ == "__main__":
    generate_ship_data_json()
