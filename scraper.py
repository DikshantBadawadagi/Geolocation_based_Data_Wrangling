import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Selenium WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

def scrape_usc_housing():
    url = "https://housing.usc.edu"
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Example: Scrape building data (adjust selectors based on actual HTML)
    buildings = []
    # Assuming buildings are listed in a table or div
    for item in soup.select(".building-item"):  # Update selector
        name = item.select_one(".building-name").text.strip()
        address = item.select_one(".building-address").text.strip()
        buildings.append({"name": name, "address": address, "source": "USC Housing"})
    
    return buildings

def scrape_usc_village():
    url = "https://village.usc.edu"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Example: Scrape USC Village buildings
    buildings = [
        {"name": "USC Village Parking", "address": "3215 South Hoover Street, Los Angeles, CA 90007", "source": "USC Village"}
    ]
    # Add more parsing logic for retail, fitness, etc.
    
    return buildings

def scrape_greek_houses():
    url = "https://greeklife.usc.edu/chapters"
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    
    # Example: Scrape fraternity/sorority houses
    buildings = []
    for item in soup.select(".chapter-item"):  # Update selector
        name = item.select_one(".chapter-name").text.strip()
        address = item.select_one(".chapter-address").text.strip() if item.select_one(".chapter-address") else "Unknown"
        buildings.append({"name": name, "address": address, "source": "Greek Life"})
    
    return buildings

def save_raw_data(data, filename="raw_buildings.csv"):
    df = pd.DataFrame(data)
    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(f"data/raw/{filename}", index=False)
    print(f"Saved raw data to data/raw/{filename}")

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