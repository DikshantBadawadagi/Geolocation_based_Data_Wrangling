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
import warnings
from shapely.errors import ShapelyDeprecationWarning

# Suppress Shapely warnings
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize Selenium WebDriver
options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--disable-gpu')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

def save_page_source(url, filename):
    try:
        driver.get(url)
        time.sleep(5)
        safe_filename = re.sub(r'[^\w\-_\.]', '_', filename)[:100]
        os.makedirs("data/raw", exist_ok=True)
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
        building_links = []
        dropdown = soup.select_one(".dropdown-menu.fullwidth-menu")
        if dropdown:
            for link in dropdown.select("a[href*='/index.php/buildings/']"):
                href = link.get("href")
                if href.startswith("/"):
                    href = base_url + href
                building_name = link.text.strip() or href.split("/")[-2].replace("-", " ").title()
                building_links.append({"name": building_name, "url": href})
        building_links = [dict(t) for t in {tuple(d.items()) for d in building_links}]
        for building in building_links:
            try:
                logging.info(f"Scraping building: {building['name']} at {building['url']}")
                response = requests.get(building["url"], headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
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
        greek_url = f"{base_url}/index.php/greek-life"
        try:
            logging.info(f"Scraping Greek housing from {greek_url}")
            response = requests.get(greek_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select(".greek-house"):
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
        for chapter in chapter_links:
            retries = 3
            for attempt in range(retries):
                try:
                    logging.info(f"Visiting chapter: {chapter['name']} at {chapter['url']}")
                    driver.get(chapter['url'])
                    safe_name = re.sub(r'[^\w\-_\.]', '_', chapter['name'])[:50]
                    save_page_source(chapter['url'], f"greek_{safe_name}.html")
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
    max_markers = 50
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        save_page_source(url, "map_page.html")
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[aria-label*='Open Location']"))
            )
        except TimeoutException:
            logging.error("Timeout waiting for map markers")
            return buildings
        markers = driver.find_elements(By.CSS_SELECTOR, "div[aria-label*='Open Location']")
        logging.info(f"Found {len(markers)} map markers")
        for i, marker in enumerate(markers[:max_markers]):
            name = "Unknown"
            try:
                name = marker.get_attribute("aria-label").replace("Open Location: ", "").strip()
                if name:
                    driver.execute_script("arguments[0].click();", marker)
                    time.sleep(2)
                    popup = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".bln-modal"))
                    )
                    popup_html = popup.get_attribute("innerHTML")
                    logging.info(f"Pop-up HTML for {name}: {popup_html[:200]}...")
                    soup = BeautifulSoup(popup_html, "html.parser")
                    # Broaden address selectors
                    address_elem = (soup.select_one("p.address") or
                                   soup.select_one("div.balloon-address") or
                                   soup.select_one(".balloon-details p") or
                                   soup.select_one(".scroll-wrapper p") or
                                   soup.select_one("p") or
                                   soup.select_one("span"))
                    address = address_elem.text.strip() if address_elem else "Unknown"
                    logging.info(f"Initial address for {name}: {address}")
                    if address == "Unknown" or not address:
                        try:
                            # Try Directions button or link
                            directions_btn = (driver.find_element(By.ID, "openDirections") or
                                            driver.find_element(By.CSS_SELECTOR, "a[href*='directions']") or
                                            driver.find_element(By.CSS_SELECTOR, "button[data-action='directions']"))
                            driver.execute_script("arguments[0].click();", directions_btn)
                            time.sleep(2)
                            popup = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".bln-modal"))
                            )
                            popup_html = popup.get_attribute("innerHTML")
                            logging.info(f"Directions pop-up HTML for {name}: {popup_html[:200]}...")
                            soup = BeautifulSoup(popup_html, "html.parser")
                            address_elem = (soup.select_one("p.address") or
                                           soup.select_one("div.balloon-address") or
                                           soup.select_one(".scroll-wrapper p") or
                                           soup.select_one("p") or
                                           soup.select_one("span"))
                            address = address_elem.text.strip() if address_elem else "Unknown"
                            logging.info(f"Directions address for {name}: {address}")
                        except:
                            logging.info(f"No Directions button for {name}")
                    # Relaxed regex for address validation
                    if address != "Unknown" and not re.match(r'^\d+.*,\s*Los Angeles\s*,?\s*CA\s*\d{5}', address, re.IGNORECASE):
                        logging.warning(f"Invalid address format for {name}: {address}")
                        address = "Unknown"
                    buildings.append({
                        "name": name,
                        "address": address,
                        "source": "USC Map"
                    })
                    try:
                        close_btn = driver.find_element(By.ID, "close-balloon-details")
                        driver.execute_script("arguments[0].click();", close_btn)
                        time.sleep(1)
                    except:
                        logging.info(f"No close button for {name}")
            except Exception as e:
                logging.error(f"Error processing map marker {i+1} ({name}): {str(e)}")
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
        logging.info("Scraping OSM buildings for USC")
        place = "University of Southern California, Los Angeles, CA"
        tags = {"building": True}
        max_retries = 3
        for attempt in range(max_retries):
            try:
                gdf = ox.features_from_place(place, tags=tags)
                logging.info(f"Retrieved {len(gdf)} OSM building features")
                logging.info(f"OSM columns: {list(gdf.columns)}")
                logging.info(f"OSM sample: {gdf[['name', 'addr:street', 'addr:housenumber']].head().to_dict()}")
                break
            except Exception as e:
                logging.error(f"Attempt {attempt+1} failed fetching OSM buildings: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error("Max retries reached for OSM buildings")
                    return buildings
                time.sleep(5)
        for _, row in gdf.iterrows():
            try:
                name = row.get("name", "Unknown")
                street = row.get("addr:street", "")
                city = row.get("addr:city", "Los Angeles")
                postcode = row.get("addr:postcode", "90007")
                housenumber = row.get("addr:housenumber", "")
                address = f"{housenumber} {street}, {city}, CA {postcode}".strip(", ")
                # Include all named buildings
                if name != "Unknown":
                    buildings.append({
                        "name": name,
                        "address": address if street and housenumber else "Unknown",
                        "source": "OpenStreetMap"
                    })
            except Exception as e:
                logging.error(f"Error processing OSM building {row.get('name', 'Unknown')}: {str(e)}")
                continue
        uni_tags = {"amenity": "university"}
        for attempt in range(max_retries):
            try:
                gdf_uni = ox.features_from_place(place, tags=uni_tags)
                logging.info(f"Retrieved {len(gdf_uni)} OSM university features")
                logging.info(f"University OSM columns: {list(gdf_uni.columns)}")
                logging.info(f"University OSM sample: {gdf_uni[['name', 'addr:street', 'addr:housenumber']].head().to_dict()}")
                break
            except Exception as e:
                logging.error(f"Attempt {attempt+1} failed fetching OSM university features: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error("Max retries reached for OSM university features")
                    return buildings
                time.sleep(5)
        for _, row in gdf_uni.iterrows():
            try:
                name = row.get("name", "Unknown")
                street = row.get("addr:street", "")
                city = row.get("addr:city", "Los Angeles")
                postcode = row.get("addr:postcode", "90007")
                housenumber = row.get("addr:housenumber", "")
                address = f"{housenumber} {street}, {city}, CA {postcode}".strip(", ")
                if name != "Unknown":
                    buildings.append({
                        "name": name,
                        "address": address if street and housenumber else "Unknown",
                        "source": "OpenStreetMap"
                    })
            except Exception as e:
                logging.error(f"Error processing OSM university feature {row.get('name', 'Unknown')}: {str(e)}")
                continue
        if not buildings:
            logging.warning("No valid buildings found in OSM data for USC.")
        else:
            logging.info(f"Collected {len(buildings)} OSM buildings")
    except Exception as e:
        logging.error(f"Error scraping OSM buildings: {str(e)}")
    return buildings

def save_raw_data(data, filename="raw_buildings.csv"):
    df = pd.DataFrame(data)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(f"data/raw/{filename}", index=False)
    logging.info(f"Saved raw data to data/raw/{filename}")

def main():
    housing_data = scrape_usc_housing_buildings()
    village_data = scrape_usc_village()
    greek_data = scrape_greek_houses()
    map_data = scrape_usc_map()
    osm_data = scrape_osm_buildings()
    all_data = housing_data + village_data + greek_data + map_data + osm_data
    save_raw_data(all_data)
    driver.quit()

if __name__ == "__main__":
    main()