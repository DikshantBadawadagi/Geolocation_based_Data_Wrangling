import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import osmnx as ox
import os
from dotenv import load_dotenv
import logging
import time
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize Selenium WebDriver with options
options = webdriver.ChromeOptions()
options.add_argument('--headless')  # Enable headless mode
options.add_argument('--disable-gpu')  # Disable GPU for headless
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def save_page_source(url, filename):
    """Save page source for debugging"""
    try:
        driver.get(url)
        time.sleep(5)  # Wait for page to load
        safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)[:100]  # Sanitize filename
        with open(f"data/raw/{safe_filename}", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logging.info(f"Saved page source to data/raw/{safe_filename}")
    except Exception as e:
        logging.error(f"Error saving page source for {url}: {str(e)}")

def scrape_usc_housing():
    url = "https://housing.usc.edu"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "housing_page.html")
        WebDriverWait(driver, 20).until(
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
    problematic_urls = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "greek_page.html")
        
        # Wait for chapter list to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".fl-rich-text"))
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        chapter_links = []
        for rich_text in soup.select(".fl-rich-text p"):
            links = rich_text.select("a")
            for link in links:
                chapter_name = link.text.strip()
                chapter_url = link.get("href")
                # Filter for valid chapter URLs
                if (chapter_name and chapter_url and 
                    "/prospective-students/chapters/" in chapter_url and
                    not chapter_url.startswith("mailto:") and
                    chapter_url.startswith("http")):
                    chapter_links.append({"name": chapter_name, "url": chapter_url})
        
        # Visit each chapter page to confirm existence (no address extraction)
        for chapter in chapter_links:
            retries = 3
            for attempt in range(retries):
                try:
                    logging.info(f"Visiting chapter: {chapter['name']} at {chapter['url']}")
                    driver.get(chapter['url'])
                    safe_name = re.sub(r'[^\w\-_\.]', '_', chapter['name'])[:50]
                    save_page_source(chapter['url'], f"greek_{safe_name}.html")
                    
                    # Wait for content to load
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".fl-rich-text"))
                    )
                    
                    buildings.append({
                        "name": chapter['name'],
                        "address": "Unknown",  # Addresses not available on chapter pages
                        "source": "Greek Life"
                    })
                    break  # Exit retry loop on success
                
                except (TimeoutException, WebDriverException) as e:
                    logging.error(f"Attempt {attempt+1} failed for {chapter['name']}: {str(e)}")
                    if attempt == retries - 1:
                        logging.error(f"Failed to scrape {chapter['name']} after {retries} attempts")
                        buildings.append({
                            "name": chapter['name'],
                            "address": "Unknown",
                            "source": "Greek Life"
                        })
                        problematic_urls.append(chapter['url'])
                    time.sleep(3)  # Wait before retry
        
        if not buildings:
            logging.warning("No Greek houses found. Check selectors or page content.")
        
        # Save problematic URLs
        if problematic_urls:
            with open("data/raw/problematic_urls.txt", "w") as f:
                f.write("\n".join(problematic_urls))
            logging.info("Saved problematic URLs to data/raw/problematic_urls.txt")
        
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
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label*='Open Location']"))
        )
        
        # Find and click markers to access pop-ups
        markers = driver.find_elements(By.CSS_SELECTOR, "div[aria-label*='Open Location']")
        for marker in markers:
            try:
                name = marker.get_attribute("aria-label").replace("Open Location: ", "").strip()
                if name:
                    # Click marker to open pop-up
                    driver.execute_script("arguments[0].click();", marker)
                    time.sleep(2)  # Wait for pop-up
                    # Try to extract address from pop-up (adjust selector after inspection)
                    popup = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".popup-content"))  # Placeholder
                    )
                    soup = BeautifulSoup(popup.get_attribute("innerHTML"), "html.parser")
                    address_elem = soup.select_one("p.address")  # Placeholder
                    address = address_elem.text.strip() if address_elem else "Unknown"
                    
                    buildings.append({
                        "name": name,
                        "address": address,
                        "source": "USC Map"
                    })
            except Exception as e:
                logging.error(f"Error processing map marker {name}: {str(e)}")
                buildings.append({
                    "name": name,
                    "address": "Unknown",
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
        logging.info("Scraping OSM buildings for USC Greek Row")
        # Expanded bounding box for 28th/29th Streets (Greek Row)
        north, south, east, west = 34.029, 34.017, -118.277, -118.293
        tags = {"building": True}
        gdf = ox.features_from_bbox(north, south, east, west, tags=tags)
        for _, row in gdf.iterrows():
            name = row.get("name", "Unknown")
            street = row.get("addr:street", "")
            city = row.get("addr:city", "Los Angeles")
            postcode = row.get("addr:postcode", "90007")  # Greek Row zip
            housenumber = row.get("addr:housenumber", "")
            address = f"{housenumber} {street}, {city}, CA {postcode}".strip(", ")
            # Only include if address is reasonably complete
            if street and housenumber:
                buildings.append({
                    "name": name,
                    "address": address,
                    "source": "OpenStreetMap"
                })
        if not buildings:
            logging.warning("No complete building addresses found in OSM data for Greek Row.")
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