import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import osmnx as ox
import os
from dotenv import load_dotenv
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize Selenium WebDriver with options
options = webdriver.ChromeOptions()
# options.add_argument('--headless')  # Comment out for debugging
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def save_page_source(url, filename):
    """Save page source for debugging"""
    driver.get(url)
    time.sleep(5)  # Wait for page to load
    with open(f"data/raw/{filename}", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logging.info(f"Saved page source to data/raw/{filename}")

def scrape_usc_housing():
    url = "https://housing.usc.edu"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "housing_page.html")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".housing-unit"))  # Placeholder
        )
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for item in soup.select(".housing-unit"):
            name = item.select_one(".building-name").text.strip() if item.select_one(".building-name") else "Unknown"
            address = item.select_one(".building-address").text.strip() if item.select_one(".building-address") else "Unknown"
            buildings.append({"name": name, "address": address, "source": "USC Housing"})
        if not buildings:
            logging.warning("No buildings found on USC Housing page. Check selectors or page content.")
    except Exception as e:
        logging.error(f"Error scraping USC Housing: {str(e)}")
    return buildings

def scrape_usc_village():
    url = "https://village.usc.edu"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        buildings.append({
            "name": "USC Village Parking",
            "address": "3215 South Hoover Street, Los Angeles, CA 90007",
            "source": "USC Village"
        })
    except Exception as e:
        logging.error(f"Error scraping USC Village: {str(e)}")
    return buildings

def scrape_greek_houses():
    url = "https://greeklife.usc.edu/prospective-students/chapters-2/"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "greek_page.html")
        
        # Wait for chapter list to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".fl-rich-text"))
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        chapter_links = []
        for rich_text in soup.select(".fl-rich-text p"):
            links = rich_text.select("a")
            for link in links:
                chapter_name = link.text.strip()
                chapter_url = link.get("href")
                if chapter_name and chapter_url:
                    chapter_links.append({"name": chapter_name, "url": chapter_url})
        
        # Visit each chapter page to get address
        for chapter in chapter_links:
            try:
                logging.info(f"Scraping chapter: {chapter['name']} at {chapter['url']}")
                driver.get(chapter['url'])
                save_page_source(chapter['url'], f"greek_{chapter['name'].replace(' ', '_')}.html")
                
                # Wait for content to load (update selector after inspection)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".fl-rich-text"))
                )
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                address_elem = soup.select_one(".fl-rich-text p")  # Placeholder; update after inspection
                address = address_elem.text.strip() if address_elem else "Unknown"
                
                # Clean address (basic cleaning, improve after inspection)
                if "Address:" in address:
                    address = address.split("Address:")[1].strip()
                elif not address.startswith("Unknown"):
                    address = address  # Adjust based on actual format
                
                buildings.append({
                    "name": chapter['name'],
                    "address": address,
                    "source": "Greek Life"
                })
                
            except Exception as e:
                logging.error(f"Error scraping chapter {chapter['name']}: {str(e)}")
                buildings.append({
                    "name": chapter['name'],
                    "address": "Unknown",
                    "source": "Greek Life"
                })
        
        if not buildings:
            logging.warning("No Greek houses found. Check selectors or page content.")
        
    except Exception as e:
        logging.error(f"Error scraping Greek Houses: {str(e)}")
    
    return buildings

def scrape_usc_map():
    url = "https://maps.usc.edu/?id=1928"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "map_page.html")
        
        # Wait for map markers to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label*='Open Location']"))
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        markers = soup.select("div[aria-label*='Open Location']")
        for marker in markers:
            name = marker.get("aria-label", "").replace("Open Location: ", "").strip()
            if name:
                buildings.append({
                    "name": name,
                    "address": "Unknown",  # Addresses not directly available
                    "source": "USC Map"
                })
        
        if not buildings:
            logging.warning("No buildings found on USC Map. Check selectors or page content.")
        
    except Exception as e:
        logging.error(f"Error scraping USC Map: {str(e)}")
    
    return buildings

def scrape_osm_buildings():
    buildings = []
    try:
        logging.info("Scraping OSM buildings for USC")
        place = "University of Southern California, Los Angeles, CA"
        tags = {"building": True}
        gdf = ox.geometries_from_place(place, tags=tags)
        for _, row in gdf.iterrows():
            name = row.get("name", "Unknown")
            street = row.get("addr:street", "")
            city = row.get("addr:city", "Los Angeles")
            postcode = row.get("addr:postcode", "90089")  # Default USC zip
            address = f"{street}, {city}, CA {postcode}".strip(", ")
            if name != "Unknown":
                buildings.append({
                    "name": name,
                    "address": address if street else "Unknown",
                    "source": "OpenStreetMap"
                })
        if not buildings:
            logging.warning("No buildings found in OSM data.")
    except Exception as e:
        logging.error(f"Error scraping OSM buildings: {str(e)}")
    return buildings

def save_raw_data(data, filename="raw_buildings.csv"):
    df = pd.DataFrame(data)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(f"data/raw/{filename}", index=False)
    logging.info(f"Saved raw data to data/raw/{filename}")

def main():
    # Scrape data from all sources
    # housing_data = scrape_usc_housing()  # Disabled due to 503 error
    village_data = scrape_usc_village()
    greek_data = scrape_greek_houses()
    map_data = scrape_usc_map()
    osm_data = scrape_osm_buildings()
    
    # Combine data
    all_data = village_data + greek_data + map_data + osm_data
    
    # Save raw data
    save_raw_data(all_data)
    
    # Close Selenium driver
    driver.quit()

if __name__ == "__main__":
    main()