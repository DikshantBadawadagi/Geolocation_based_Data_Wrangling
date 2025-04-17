import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
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
        
        # Save page source for debugging
        save_page_source(url, "housing_page.html")
        
        # Wait for building list to load (update selector after inspection)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".housing-unit"))  # Placeholder
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for item in soup.select(".housing-unit"):  # Placeholder
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
        
        # Hardcoded placeholder (update after inspection)
        buildings.append({
            "name": "USC Village Parking",
            "address": "3215 South Hoover Street, Los Angeles, CA 90007",
            "source": "USC Village"
        })
        
    except Exception as e:
        logging.error(f"Error scraping USC Village: {str(e)}")
    
    return buildings

def scrape_greek_houses():
    url = "https://greeklife.usc.edu/chapters"
    buildings = []
    try:
        logging.info(f"Scraping {url}")
        driver.get(url)
        
        # Save page source for debugging
        save_page_source(url, "greek_page.html")
        
        # Wait for chapter list to load (update selector after inspection)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".chapter-card"))  # Placeholder
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for item in soup.select(".chapter-card"):  # Placeholder
            name = item.select_one(".chapter-name").text.strip() if item.select_one(".chapter-name") else "Unknown"
            address = item.select_one(".chapter-address").text.strip() if item.select_one(".chapter-address") else "Unknown"
            buildings.append({"name": name, "address": address, "source": "Greek Life"})
        
        if not buildings:
            logging.warning("No Greek houses found. Check selectors or page content.")
        
    except Exception as e:
        logging.error(f"Error scraping Greek Houses: {str(e)}")
    
    return buildings

def save_raw_data(data, filename="raw_buildings.csv"):
    df = pd.DataFrame(data)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(f"data/raw/{filename}", index=False)
    logging.info(f"Saved raw data to data/raw/{filename}")

def main():
    # Scrape data from all sources
    housing_data = scrape_usc_housing()
    village_data = scrape_usc_village()
    greek_data = scrape_greek_houses()
    
    # Combine data
    all_data = housing_data + village_data + greek_data
    
    # Save raw data
    save_raw_data(all_data)
    
    # Close Selenium driver
    driver.quit()

if __name__ == "__main__":
    main()