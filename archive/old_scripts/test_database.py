#!/usr/bin/env python3
"""
Quick test script to verify database functionality.
Run this after setting up PostgreSQL to test the connection and operations.

Usage:
    PYTHONPATH=/Users/z5241339/Documents/unsw_ai_rag python3 test_database.py
"""

from database.db import init_database, upsert_staff, get_connection
from database.schema import StaffProfile


def test_database_setup():
    """Test database initialization and basic operations."""
    print("=" * 60)
    print("Testing Database Setup")
    print("=" * 60)

    # Test 1: Initialize database
    print("\n1. Initializing database tables...")
    try:
        init_database()
        print("   ✓ Database initialized successfully")
    except Exception as e:
        print(f"   ✗ Error initializing database: {e}")
        return False

    # Test 2: Insert test data
    print("\n2. Inserting test data...")
    test_data = [
        {
            "email": "test.user1@unsw.edu.au",
            "first_name": "Test",
            "last_name": "User1",
            "full_name": "Dr Test User1",
            "role": "Senior Lecturer",
            "faculty": "Engineering",
            "school": "Computer Science and Engineering",
            "profile_url": "https://example.com/test1",
            "biography": "This is a test biography.",
            "research_text": "AI, Machine Learning"
        },
        {
            "email": "test.user2@unsw.edu.au",
            "first_name": "Test",
            "last_name": "User2",
            "full_name": "Professor Test User2",
            "role": "Professor",
            "faculty": "Engineering",
            "school": "Electrical Engineering",
            "biography": "Another test biography.",
        }
    ]

    try:
        result = upsert_staff(test_data)
        print(f"   ✓ Inserted {result['total']} test records")
    except Exception as e:
        print(f"   ✗ Error inserting data: {e}")
        return False

    # Test 3: Query data
    print("\n3. Querying inserted data...")
    try:
        session = get_connection()
        count = session.query(StaffProfile).count()
        print(f"   ✓ Found {count} total records in database")

        # Query test records
        test_records = session.query(StaffProfile).filter(
            StaffProfile.email.like('test.%@unsw.edu.au')
        ).all()

        print(f"   ✓ Found {len(test_records)} test records")

        for record in test_records:
            print(f"      - {record.full_name} ({record.email})")

        session.close()
    except Exception as e:
        print(f"   ✗ Error querying data: {e}")
        return False

    # Test 4: Update existing record (upsert)
    print("\n4. Testing update (upsert) functionality...")
    updated_data = [
        {
            "email": "test.user1@unsw.edu.au",
            "first_name": "Updated",
            "last_name": "User1",
            "full_name": "Dr Updated User1",
            "role": "Associate Professor",  # Changed
            "faculty": "Engineering",
            "school": "Computer Science and Engineering",
            "biography": "This biography has been updated.",  # Changed
        }
    ]

    try:
        result = upsert_staff(updated_data)
        print(f"   ✓ Upserted {result['total']} records")

        # Verify update
        session = get_connection()
        updated_record = session.query(StaffProfile).filter(
            StaffProfile.email == "test.user1@unsw.edu.au"
        ).first()

        if updated_record and updated_record.role == "Associate Professor":
            print(f"   ✓ Record updated successfully: {updated_record.full_name} is now {updated_record.role}")
        else:
            print("   ✗ Record was not updated correctly")

        session.close()
    except Exception as e:
        print(f"   ✗ Error updating data: {e}")
        return False

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nDatabase is ready for importing real staff data.")
    print("Run: PYTHONPATH=/Users/z5241339/Documents/unsw_ai_rag python3 scripts/import_to_database.py")
    return True


def cleanup_test_data():
    """Remove test data from database."""
    print("\n" + "=" * 60)
    print("Cleaning up test data...")
    try:
        session = get_connection()
        deleted = session.query(StaffProfile).filter(
            StaffProfile.email.like('test.%@unsw.edu.au')
        ).delete()
        session.commit()
        print(f"✓ Deleted {deleted} test records")
        session.close()
    except Exception as e:
        print(f"✗ Error cleaning up: {e}")


if __name__ == "__main__":
    import sys

    try:
        success = test_database_setup()

        if success:
            # Ask if user wants to clean up test data
            response = input("\nClean up test data? (y/n): ").lower().strip()
            if response == 'y':
                cleanup_test_data()
            else:
                print("Test data kept in database.")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
