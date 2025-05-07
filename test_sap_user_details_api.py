#!/usr/bin/env python
"""
Script to test the SAP user details API endpoint.
"""

import argparse
import json
import requests

def test_sap_user_details_api(base_url, org_id, user_id, token=None):
    """
    Test the SAP user details API endpoint.
    
    Args:
        base_url (str): Base URL of the edX instance (e.g., http://localhost:18000)
        org_id (str): SAP organization ID
        user_id (str): SAP user ID
        token (str, optional): Authentication token if needed
    """
    url = f"{base_url}/api/v1/sap_success_factors/user-details/"
    
    headers = {}
    if token:
        headers['Authorization'] = f'JWT {token}'
    
    params = {
        'org_id': org_id,
        'loggedinuserid': user_id
    }
    
    print(f"Making request to {url} with params {params}")
    
    try:
        response = requests.get(url, params=params, headers=headers)
        
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("\nUser details retrieved successfully:")
            print(f"Email: {data.get('email')}")
            print(f"Name: {data.get('given_name')} {data.get('surname')}")
            print("\nFull response data:")
            print(json.dumps(data, indent=2))
        else:
            print("Error response:")
            try:
                print(json.dumps(response.json(), indent=2))
            except ValueError:
                print(response.text)
                
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the SAP user details API endpoint")
    parser.add_argument("--base-url", default="http://localhost:18000", help="Base URL of the edX instance")
    parser.add_argument("--org-id", required=True, help="SAP organization ID")
    parser.add_argument("--user-id", required=True, help="SAP user ID")
    parser.add_argument("--token", help="JWT token (if needed)")
    
    args = parser.parse_args()
    
    test_sap_user_details_api(args.base_url, args.org_id, args.user_id, args.token) 