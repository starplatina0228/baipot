
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
            # Use DictReader to easily access columns by name
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Clean up keys and values if necessary
                cleaned_row = {k.strip(): v.strip() for k, v in row.items()}
                
                # Extract relevant data
                shipping_company = cleaned_row.get('선사')
                
                if shipping_company:
                    ship_info = {
                        'call_sign': cleaned_row.get('호출부호'),
                        'ship_name': cleaned_row.get('선명'),
                        'gross_tonnage': int(cleaned_row.get('총톤수', 0)),
                        'LOA': int(cleaned_row.get('LOA', 0))
                    }
                    ship_data_by_company[shipping_company].append(ship_info)

        # Convert defaultdict to a regular dict and save to a JSON file
        output_path = 'backend/ship_data.json'
        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(dict(ship_data_by_company), jsonfile, indent=2, ensure_ascii=False)
        print(f"Successfully created {output_path}")

    except FileNotFoundError:
        print(json.dumps({"error": "ship_info.csv not found in backend directory."}, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))

if __name__ == "__main__":
    generate_ship_data_json()
