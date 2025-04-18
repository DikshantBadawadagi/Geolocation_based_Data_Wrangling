import pandas as pd
import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import time
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize geocoder
geolocator = Nominatim(user_agent="usc_building_mapper")

def is_complete_address(address):
    """Check if address is complete (matches 'number street, Los Angeles, CA 900xx')."""
    if pd.isna(address) or address == "Unknown":
        return False
    if isinstance(address, str):
        # Match: "642 West 34th Street, Los Angeles, CA 90089" or similar
        return bool(re.match(r'^\d+.*,\s*Los Angeles\s*,?\s*CA\s*\d{5}$', address, re.IGNORECASE))
    return False

def geocode_address(address):
    """Geocode address using Nominatim."""
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return location.latitude, location.longitude
        else:
            logging.warning(f"Geocoding failed for address: {address}")
            return None, None
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        logging.error(f"Geocoding error for address {address}: {str(e)}")
        return None, None

def geocode_buildings(input_csv, output_csv):
    try:
        logging.info(f"Reading input CSV: {input_csv}")
        df = pd.read_csv(input_csv)
        
        logging.info(f"Total rows: {len(df)}")
        
        # Geocode only complete addresses
        logging.info("Geocoding complete addresses...")
        for idx, row in df.iterrows():
            address = row['address']
            # Skip if already geocoded or not a complete address
            if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                logging.info(f"Skipping geocoding for {row['name']} (already geocoded)")
                continue
            if not is_complete_address(address):
                logging.info(f"Skipping geocoding for {row['name']} (incomplete address: {address})")
                continue
            lat, lon = geocode_address(address)
            df.at[idx, 'latitude'] = lat
            df.at[idx, 'longitude'] = lon
            time.sleep(1)  # Respect Nominatim rate limit
        
        # Save geocoded data
        logging.info(f"Saving geocoded data to {output_csv}")
        df.to_csv(output_csv, index=False)
        logging.info(f"Geocoding complete. Output saved to {output_csv}")
        
        return df
    except Exception as e:
        logging.error(f"Error geocoding buildings: {str(e)}")
        raise

def main():
    input_csv = "data/processed/cleaned_buildings.csv"
    output_csv = "data/processed/geocoded_buildings.csv"
    df = geocode_buildings(input_csv, output_csv)
    logging.info(f"Geocoded {len(df)} buildings")

if __name__ == "__main__":
    main()