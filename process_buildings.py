import pandas as pd
import re
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize geocoder
geolocator = Nominatim(user_agent="usc_task")

def classify_location(row):
    """Classify a location based on name and source."""
    name = row['name'].lower()
    source = row['source']
    
    # Residence Halls: All USC Housing entries
    if source == 'USC Housing':
        return 'Residence Hall'
    
    # Greek Houses: All Greek Life entries
    if source == 'Greek Life':
        return 'Greek House'
    
    # Parking: Names containing 'parking', 'lot', 'garage'
    if any(keyword in name for keyword in ['parking', 'lot', 'garage']):
        return 'Parking'
    
    # Academic Buildings: USC Map entries with academic-related names
    academic_keywords = ['hall', 'center', 'building', 'lecture', 'gerontology', 'campus']
    if source == 'USC Map' and any(keyword in name for keyword in academic_keywords):
        return 'Academic Building'
    
    # Other: Remaining entries (e.g., Los Angeles Fire Dept Station 15)
    return 'Other'

def geocode_address(address):
    """Geocode an address to get latitude and longitude."""
    if address == 'Unknown' or pd.isna(address):
        return None, None
    
    try:
        # Clean address for geocoding
        address = re.sub(r'\s+', ' ', address.strip())
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            logging.warning(f"Geocoding failed for address: {address}")
            return None, None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logging.error(f"Geocoding error for {address}: {str(e)}")
        return None, None

def process_buildings(input_csv, output_csv):
    # Read CSV
    df = pd.read_csv(input_csv)
    
    # Add category column
    df['category'] = df.apply(classify_location, axis=1)
    
    # Add latitude and longitude columns
    df['latitude'] = None
    df['longitude'] = None
    
    # Geocode addresses
    for idx, row in df.iterrows():
        if row['address'] != 'Unknown':
            lat, lon = geocode_address(row['address'])
            df.at[idx, 'latitude'] = lat
            df.at[idx, 'longitude'] = lon
            time.sleep(1)  # Respect Nominatim rate limits
    
    # Clean data: Remove duplicates, ensure consistent address format
    df = df.drop_duplicates(subset=['name', 'address'])
    df['address'] = df['address'].str.title()  # Capitalize address words
    
    # Save to CSV
    df.to_csv(output_csv, index=False)
    logging.info(f"Saved processed data to {output_csv}")
    
    return df

def main():
    input_csv = "data/raw/raw_buildings.csv"
    output_csv = "data/processed/cleaned_buildings.csv"
    
    # Ensure output directory exists
    import os
    os.makedirs("data/processed", exist_ok=True)
    
    # Process buildings
    df = process_buildings(input_csv, output_csv)
    
    # Log summary
    logging.info(f"Total rows: {len(df)}")
    logging.info(f"Categories:\n{df['category'].value_counts()}")
    logging.info(f"Geocoded addresses: {df['latitude'].notnull().sum()}")
    logging.info(f"Unknown addresses: {df['address'].eq('Unknown').sum()}")

if __name__ == "__main__":
    main()