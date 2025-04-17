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

def scrape_usc_housing_buildings():
    buildings = []
    base_url = "https://housing.usc.edu"
    home_url = base_url
    
    try:
        logging.info(f"Scraping housing options from {home_url}")
        response = requests.get(home_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find building links in dropdown
        building_links = []
        dropdown = soup.select_one(".dropdown-menu.fullwidth-menu")
        if dropdown:
            for link in dropdown.select("a[href*='/index.php/buildings/']"):
                href = link.get("href")
                if href.startswith("/"):
                    href = base_url + href
                building_name = link.text.strip() or href.split("/")[-2].replace("-", " ").title()
                building_links.append({"name": building_name, "url": href})
        
        # Remove duplicates
        building_links = [dict(t) for t in {tuple(d.items()) for d in building_links}]
        
        # Scrape each building page
        for building in building_links:
            try:
                logging.info(f"Scraping building: {building['name']} at {building['url']}")
                response = requests.get(building["url"], headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Extract address
                address_elem = soup.select_one(".building-address p")
                address = address_elem.text.strip().replace("\n", ", ") if address_elem else "Unknown"
                
                buildings.append({
                    "name": building["name"],
                    "address": address,
                    "source": "USC Housing"
                })
            except Exception as e:
                logging.error(f"Error scraping {building['name']}: {str(e)}")
                buildings.append({
                    "name": building["name"],
                    "address": "Unknown",
                    "source": "USC Housing"
                })
        
        # Try Greek housing page
        greek_url = f"{base_url}/index.php/greek-life"
        try:
            logging.info(f"Scraping Greek housing from {greek_url}")
            response = requests.get(greek_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            for item in soup.select(".greek-house"):  # Placeholder selector
                name = item.select_one(".chapter-name").text.strip() if item.select_one(".chapter-name") else "Unknown"
                address = item.select_one(".building-address p").text.strip().replace("\n", ", ") if item.select_one(".building-address p") else "Unknown"
                buildings.append({
                    "name": name,
                    "address": address,
                    "source": "USC Greek Housing"
                })
        except Exception as e:
            logging.error(f"Error scraping Greek housing: {str(e)}")
        
        if not buildings:
            logging.warning("No buildings found on USC Housing pages.")
        
    except Exception as e:
        logging.error(f"Error scraping housing options: {str(e)}")
    
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
                if (chapter_name and chapter_url and 
                    "/prospective-students/chapters/" in chapter_url and
                    not chapter_url.startswith("mailto:") and
                    chapter_url.startswith("http")):
                    chapter_links.append({"name": chapter_name, "url": chapter_url})
        
        # Visit each chapter page
        for chapter in chapter_links:
            retries = 3
            for attempt in range(retries):
                try:
                    logging.info(f"Visiting chapter: {chapter['name']} at {chapter['url']}")
                    driver.get(chapter['url'])
                    safe_name = re.sub(r'[^\w\-_\.]', '_', chapter['name'])[:50]
                    save_page_source(chapter['url'], f"greek_{safe_name}.html")
                    
                    # Wait for content
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".fl-rich-text"))
                    )
                    
                    buildings.append({
                        "name": chapter['name'],
                        "address": "Unknown",
                        "source": "Greek Life"
                    })
                    break
                
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
                    time.sleep(3)
        
        if not buildings:
            logging.warning("No Greek houses found.")
        
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
        save_page_source(url, "greek_page.html")
        
        # Wait for map markers
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label*='Open Location']"))
        )
        
        # Find markers
        markers = driver.find_elements(By.CSS_SELECTOR, "div[aria-label*='Open Location']")
        for marker in markers:
            try:
                name = marker.get_attribute("aria-label").replace("Open Location: ", "").strip()
                if name:
                    # Click marker
                    driver.execute_script("arguments[0].click();", marker)
                    time.sleep(5)
                    
                    # Try pop-up
                    popup = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".bln-modal"))
                    )
                    soup = BeautifulSoup(popup.get_attribute("innerHTML"), "html.parser")
                    
                    # Try address selectors
                    address_elem = (soup.select_one("p.address") or
                                  soup.select_one(".balloon-details p") or
                                  soup.select_one(".scroll-wrapper p"))
                    address = address_elem.text.strip() if address_elem else "Unknown"
                    
                    # Try directions
                    if address == "Unknown":
                        try:
                            directions_btn = driver.find_element(By.ID, "openDirections")
                            directions_btn.click()
                            time.sleep(3)
                            popup = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".bln-modal"))
                            )
                            soup = BeautifulSoup(popup.get_attribute("innerHTML"), "html.parser")
                            address_elem = soup.select_one("p.address") or soup.select_one(".scroll-wrapper p")
                            address = address_elem.text.strip() if address_elem else "Unknown"
                        except:
                            pass
                    
                    # Validate address
                    if address != "Unknown" and not re.match(r'^\d+.*,\s*Los Angeles,\s*CA\s*\d{5}', address):
                        address = "Unknown"
                    
                    buildings.append({
                        "name": name,
                        "address": address,
                        "source": "USC Map"
                    })
                    
                    # Close pop-up
                    try:
                        close_btn = driver.find_element(By.ID, "close-balloon-details")
                        close_btn.click()
                        time.sleep(1)
                    except:
                        pass
                
            except Exception as e:
                logging.error(f"Error processing map marker {name}: {str(e)}")
                buildings.append({
                    "name": name,
                    "address": "Unknown",
                    "source": "USC Map"
                })
        
        if not buildings:
            logging.warning("No buildings found on USC Map.")
        
    except Exception as e:
        logging.error(f"Error scraping USC Map: {str(e)}")
    
    return buildings

def scrape_osm_buildings():
    buildings = []
    try:
        logging.info("Scraping OSM buildings for USC and Greek Row")
        # Bounding box for USC campus and Greek Row
        north, south, east, west = 34.031, 34.015, -118.275, -118.295
        tags = {
            "building": True,
            "destination": ["fraternity", "sorority"]
        }
        # Corrected call to features_from_bbox
        gdf = ox.features.features_from_bbox(bbox=(north, south, east, west), tags=tags)
        for _, row in gdf.iterrows():
            name = row.get("name", "Unknown")
            street = row.get("addr:street", "")
            city = row.get("addr:city", "Los Angeles")
            postcode = row.get("addr:postcode", "90007")
            housenumber = row.get("addr:housenumber", "")
            address = f"{housenumber} {street}, {city}, CA {postcode}".strip(", ")
            if street:
                buildings.append({
                    "name": name,
                    "address": address if housenumber else f"{street}, {city}, CA {postcode}",
                    "source": "OpenStreetMap"
                })
        if not buildings:
            logging.warning("No buildings found in OSM data for USC/Greek Row.")
    except Exception as e:
        logging.error(f"Error scraping OSM buildings: {str(e)}")
    return buildings

def save_raw_data(data, filename="raw_buildings.csv"):
    df = pd.DataFrame(data)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(f"data/raw/{filename}", index=False)
    logging.info(f"Saved raw data to data/raw/{filename}")

def main():
    # Scrape data
    housing_data = scrape_usc_housing_buildings()
    village_data = scrape_usc_village()
    greek_data = scrape_greek_houses()
    map_data = scrape_usc_map()
    osm_data = scrape_osm_buildings()
    
    # Combine data
    all_data = housing_data + village_data + greek_data + map_data + osm_data
    
    # Save raw data
    save_raw_data(all_data)
    
    # Close Selenium driver
    driver.quit()

if __name__ == "__main__":
    main()