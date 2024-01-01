import streamlit as st
import pandas as pd
import shapely.geometry
import shapely.ops
import geopy.distance
from geopy.distance import great_circle


# Function to find the closest optimal EV charger potential from dataset from the zone defined distance.
def find_closest_regional_record(df, user_coordinates):
    for _, row in df.iterrows():
        record_coordinates = (row['Latitude'], row['Longitude'])
        zone_radius_km = row['Zone (km)']
        distance = great_circle(user_coordinates, record_coordinates).km

        if distance <= zone_radius_km:
            return row
    return None

# Function to find the closest record from the dataset and calculate distance
def find_closest_record(df, user_coordinates, max_distance_km):
    closest_distance = float('inf')
    closest_record = None

    for _, row in df.iterrows():
        record_coordinates = (row['Latitude'], row['Longitude'])
        distance = great_circle(user_coordinates, record_coordinates).km
        if distance < closest_distance:
            closest_distance = distance
            closest_record = row

    # Check if the closest record is within the 10km limit
    if closest_distance > max_distance_km:
        return None

    # Add a new column for distance if a record is found
    if closest_record is not None:
        closest_record = closest_record.copy()
        closest_record['distance_km'] = closest_distance

    return closest_record




# Function to check if a point is within a radius of a line segment
def is_within_radius_of_line_segment(user_point, line_start, line_end, radius_km):
    line = shapely.geometry.LineString([line_start, line_end])
    point = shapely.geometry.Point(user_point)
    # Convert radius to degrees (approximation)
    radius_degrees = radius_km / 111.32  # rough conversion of km to degrees
    return line.distance(point) <= radius_degrees

# Add this function to filter rows based on line segments
def filter_locations_with_lines(df, user_coordinates, radius_km):
    return df[df.apply(lambda row: 
                       not pd.isna(row['latitude']) and not pd.isna(row['longitude']) and (
                       calculate_distance(user_coordinates, (row['latitude'], row['longitude'])) <= radius_km or 
                       (not pd.isna(row['latitude_end']) and not pd.isna(row['longitude_end']) and (
                        calculate_distance(user_coordinates, (row['latitude_end'], row['longitude_end'])) <= radius_km or 
                        is_within_radius_of_line_segment(user_coordinates, (row['latitude'], row['longitude']), (row['latitude_end'], row['longitude_end']), radius_km)))), 
                       axis=1)]

# Function to calculate the distance between two coordinates
def calculate_distance(coord1, coord2):
    return geopy.distance.geodesic(coord1, coord2).km

# Function to filter locations within a given radius
def filter_locations_within_radius(df, user_coordinates, radius_km):
    return df[df.apply(lambda row: calculate_distance(user_coordinates, (row['latitude'], row['longitude'])) <= radius_km, axis=1)]

def main():
    
    # Load the datasets
    ev_charging_stations = pd.read_csv('consolidated_existing_chargers.csv')
    petrol_station_data = pd.read_csv('petrol_station_data.csv')
    traffic_data_2018 = pd.read_csv('traffic_data_2018.csv').rename(columns={'wgs84_latitude': 'latitude', 'wgs84_longitude': 'longitude'})
    postcode_data = pd.read_csv('australian_postcodes_coordinates.csv')
    ev_registrations = pd.read_csv('ev_registrations_2017_to_2021.csv')
    proposed_investment = pd.read_csv('proposed_investment.csv')
    annual_input_output = pd.read_csv('All_NSPs_annual_input_output_data_2023.csv')
    metro_optimal = pd.read_csv('metro_optimal.csv')
    regional_optimal = pd.read_csv('regional_optimal.csv')
    approved_chargers = pd.read_csv('approved_chargers.csv')


    # Title of the app
    st.title("EV Charger Potential")

    # Sidebar for user input
    search_option = st.sidebar.radio("Search by", ["Coordinates - For Precise Analysis", "Postcode - For Holistic Analysis"])

    if search_option == "Coordinates - For Precise Analysis":
        st.sidebar.header("You can get coordinates from google maps.")
        latitude = st.sidebar.text_input("Latitude", value="-33.778375")
        longitude = st.sidebar.text_input("Longitude", value="150.815781")
    else:
        latitude = None
        longitude = None
    
    postcode = st.sidebar.number_input("Your Postcode", min_value=1001, max_value=4385, value=2000)
    radius_km = st.sidebar.number_input("Radius in Kilometers", min_value=0, value=3)

    # Button to perform analysis
    if st.sidebar.button('Analyze Location'):
        if search_option == "Postcode - For Holistic Analysis":
            user_coordinates = tuple(postcode_data[postcode_data['postcode'] == postcode][['Lat_precise', 'Long_precise']].iloc[0])
        else:
            user_coordinates = (float(latitude), float(longitude))

        # Filtering data for each dataset
        nearby_ev_chargers = filter_locations_within_radius(ev_charging_stations, user_coordinates, radius_km)
        nearby_petrol_stations = filter_locations_within_radius(petrol_station_data, user_coordinates, radius_km)
        nearby_traffic_data = filter_locations_within_radius(traffic_data_2018, user_coordinates, radius_km)
        nearby_proposed_investment = filter_locations_within_radius(proposed_investment, user_coordinates, radius_km)
        nearby_assets = filter_locations_with_lines(annual_input_output, user_coordinates, radius_km)
        nearby_approved_chargers = filter_locations_within_radius(approved_chargers, user_coordinates, radius_km)

        # Summarizing the data
        # ev_charger_summary = nearby_ev_chargers[['Name', 'Charger type', 'stations']].groupby(['Name', 'Charger type']).agg({'stations': 'sum'}).reset_index()
        petrol_station_summary = nearby_petrol_stations['brand'].value_counts().reset_index().rename(columns={'index': 'Brand', 'brand': 'Count'})
        traffic_summary = nearby_traffic_data[['road_name', 'traffic_count']].groupby('road_name').agg({'traffic_count': 'sum'}).reset_index()
        registration_summary = ev_registrations[ev_registrations['Postcode'] == postcode]
        investment_summary = nearby_proposed_investment
        # After retrieving user_coordinates
        closest_metro_record = find_closest_record(metro_optimal, user_coordinates,3)
        # Finding the corresponding regional record
        closest_regional_record = find_closest_regional_record(regional_optimal, user_coordinates)
        


        # Displaying the summaries
        st.write("Existing EV Chargers within", radius_km, "km radius:")
        st.dataframe(nearby_ev_chargers)
        st.write("Petrol Stations within", radius_km, "km radius:")
        st.dataframe(petrol_station_summary)
        st.write("Traffic Data of busy roads within", radius_km, "km radius:")
        st.dataframe(traffic_summary)
        if not registration_summary.empty:
            st.write("EV Car Registrations for Postcode:", postcode)
            st.dataframe(registration_summary)
        else:
            st.write("No EV registration data found for Postcode:", postcode)
        st.write("Proposed Investments in Electrical Infrastructure within", radius_km, "km radius:")
        st.dataframe(nearby_proposed_investment)
        st.write("Planned Nearby electrical equiptment upgrades/repair within", radius_km, "km radius:")
        st.dataframe(nearby_assets)
        # Displaying the closest metro record
        if closest_metro_record is not None:
            st.write("Number of EV Charger plugs we need in the future (Metro):")
            st.dataframe(closest_metro_record.to_dict())
        else:
            st.write("No close records found in Metro Optimal Data")
        # Displaying the corresponding regional record
        if closest_regional_record is not None:
            st.write("Number of EV Charger plugs we need in the future (Regional):")
            st.dataframe(closest_regional_record.to_dict())
        else:
            st.write("No close records found in Regional Optimal Data within the specified zone")
        
        st.write("Approved EV Chargers soon to be built near radius")
        st.dataframe(nearby_approved_chargers)
# Change All these .dataframes to .json when using the LLM for better understanding for the LLM.
if __name__ == "__main__":
    main()