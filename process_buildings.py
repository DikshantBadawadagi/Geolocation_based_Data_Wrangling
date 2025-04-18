import pandas as pd
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Manual Greek house addresses (from Google Maps)
greek_addresses = {
    "Kappa Alpha Theta": "653 West 28th Street, Los Angeles, CA 90007",
    "Alpha Delta Pi": "647 West 28th Street, Los Angeles, CA 90007",
    "Pi Beta Phi": "655 West 28th Street, Los Angeles, CA 90007",
    "Delta Gamma": "649 West 28th Street, Los Angeles, CA 90007",
    "Kappa Kappa Gamma": "645 West 28th Street, Los Angeles, CA 90007"
}

def is_valid_address(address):
    """Check if address is valid (not 'Unknown' or containing 'nan')."""
    if pd.isna(address) or address == "Unknown":
        return False
    if isinstance(address, str):
        return not re.search(r'\bnan\b', address, re.IGNORECASE)
    return False

def classify_location(row):
    name = row['name']
    source = row['source']
    
    if pd.isna(name) or not isinstance(name, str):
        logging.warning(f"Missing or invalid name for row: {row.to_dict()}")
        return "Unknown"
    
    name = name.lower()
    if source == "USC Housing":
        if any(keyword in name for keyword in ["residential college", "housing", "dorm", "hall", "tower", "apartments", "residence"]):
            return "Residence Hall"
        return "Student Housing"
    elif source == "USC Village":
        return "Parking"
    elif source == "Greek Life":
        return "Greek House"
    elif source == "USC Map":
        if any(keyword in name for keyword in ["hall", "center", "building", "lecture", "laboratory", "library", "pavilion", "institute"]):
            return "Academic Building"
        elif any(keyword in name for keyword in ["parking", "lot", "structure", "garage"]):
            return "Parking"
        elif any(keyword in name for keyword in ["field", "stadium", "arena"]):
            return "Athletic Facility"
        return "Other"
    elif source == "OpenStreetMap":
        if any(keyword in name for keyword in ["hall", "center", "laboratory", "library", "pavilion", "building", "institute", "school", "department"]):
            return "Academic Building"
        elif any(keyword in name for keyword in ["dormitory", "residence", "housing"]):
            return "Residence Hall"
        elif any(keyword in name for keyword in ["parking", "garage"]):
            return "Parking"
        elif "university of southern california" in name:
            return "Campus"
        return "Other"
    return "Unknown"

def process_buildings(input_csv, output_csv):
    try:
        logging.info(f"Reading input CSV: {input_csv}")
        df = pd.read_csv(input_csv)
        
        # Clean name and address columns
        df['name'] = df['name'].fillna('Unknown').astype(str)
        df['address'] = df['address'].fillna('Unknown').astype(str)
        logging.info(f"Total rows: {len(df)}")
        
        # Apply Greek house addresses
        df.loc[(df['source'] == "Greek Life") & (df['name'].isin(greek_addresses)), 'address'] = df['name'].map(greek_addresses)
        
        # Clean malformed addresses (e.g., containing 'nan')
        df['address'] = df['address'].apply(lambda x: "Unknown" if re.search(r'\bnan\b', x, re.IGNORECASE) else x)
        
        # Classify locations
        logging.info("Classifying locations...")
        df['category'] = df.apply(classify_location, axis=1)
        
        # Log category distribution
        category_counts = df['category'].value_counts()
        logging.info(f"Category distribution:\n{category_counts}")
        
        # Log unclassified names by source
        for source in df['source'].unique():
            unclassified = df[(df['source'] == source) & (df['category'] == "Other")]['name'].unique()
            if len(unclassified) > 0:
                logging.info(f"Unclassified {source} names: {list(unclassified)}")
        
        # Initialize geocoding columns
        df['latitude'] = None
        df['longitude'] = None
        
        # Deduplicate
        df = df.drop_duplicates(subset=['name', 'address', 'source'], keep='first')
        logging.info(f"Rows after deduplication: {len(df)}")
        
        # Save processed data
        logging.info(f"Saving processed data to {output_csv}")
        df.to_csv(output_csv, index=False)
        logging.info(f"Processing complete. Output saved to {output_csv}")
        
        return df
    except Exception as e:
        logging.error(f"Error processing buildings: {str(e)}")
        raise

def main():
    input_csv = "data/raw/raw_buildings.csv"
    output_csv = "data/processed/cleaned_buildings.csv"
    df = process_buildings(input_csv, output_csv)
    logging.info(f"Processed {len(df)} buildings")

if __name__ == "__main__":
    main()