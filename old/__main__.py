from dotenv import load_dotenv
# from watergun.image_processing import load_crosshair, load_floor_corners
# from watergun.stream_handling import process_stream
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    load_dotenv()
    print("Hello")
    
    # load_crosshair(os.getenv('CROSSHAIR_FILE'))
    # load_floor_corners(os.getenv('FLOOR_CORNERS_FILE'))
    
    # process_stream()

if __name__ == "__main__":
    main()