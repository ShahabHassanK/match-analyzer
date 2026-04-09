import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.event_scraper import scrape_whoscored

def print_separator():
    print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    print("\n" + "🏟️  xG Match Analyzer - Phase 2 Test Suite".center(80))
    print_separator()
    
    # URL of a recent match obtained during the Phase 1 test:
    # We will use Arsenal vs Liverpool (Premier League)
    test_url = "https://www.whoscored.com/Matches/1903267/Live/Premier-League-2025-2026-Arsenal-vs-Liverpool"
    
    print(f"🚀 Initializing ClipMaker Raw Scraper...")
    print(f"   Target URL: {test_url}\n")
    
    try:
        df = scrape_whoscored(test_url)
        
        print_separator()
        print("📊 SCRAPING RESULTS")
        print_separator()
        print(f"   Successfully extracted {len(df)} discrete raw match events!\n")
        
        print("   👉 SHAPE:")
        print(f"      Rows: {df.shape[0]}")
        print(f"      Columns: {df.shape[1]}")
        print(f"      (Available columns include: x, y, endX, endY, is_box_entry_pass, xT, etc.)\n")
        
        print("   🔍 SNEAK PEEK (First 5 events):")
        # Print a clean sub-selection of the raw dataframe fields to show accuracy
        cols_to_show = ["minute", "second", "type", "team", "playerName", "x", "y"]
        print(df[cols_to_show].head().to_string(index=False))
        
        print("\n✅ Phase 2 test complete! Check the backend/data/ folder for the raw CSV.")
        
    except Exception as e:
        print(f"❌ Scraper failed: {e}")
