"""
Database Export Script for NutriLens AI
Exports database structure and sample data to JSON format
"""

import json
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from typing import Any, Dict, List
import os

# Import your config
from app.core.config import settings

# Database connection
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def serialize_value(val: Any) -> Any:
    """Convert non-JSON-serializable values to strings"""
    if isinstance(val, datetime):
        return val.isoformat()
    elif isinstance(val, bytes):
        return val.decode('utf-8', errors='ignore')
    elif val is None:
        return None
    return val


def get_table_structure(table_name: str) -> Dict[str, Any]:
    """Get column information for a table"""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    
    structure = {
        "table_name": table_name,
        "columns": []
    }
    
    for col in columns:
        col_info = {
            "name": col['name'],
            "type": str(col['type']),
            "nullable": col['nullable'],
            "primary_key": col.get('primary_key', False),
            "foreign_key": None
        }
        structure["columns"].append(col_info)
    
    # Get foreign keys
    foreign_keys = inspector.get_foreign_keys(table_name)
    for fk in foreign_keys:
        for col in structure["columns"]:
            if col["name"] in fk['constrained_columns']:
                col["foreign_key"] = {
                    "references_table": fk['referred_table'],
                    "references_column": fk['referred_columns'][0]
                }
    
    return structure


def fetch_general_table_data(table_name: str, limit: int = 10) -> List[Dict]:
    """Fetch latest N entries from general tables"""
    db = SessionLocal()
    try:
        # Get column names
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        # Determine order by column (prefer id or created_at)
        order_by = 'id'
        if 'created_at' in columns:
            order_by = 'created_at'
        
        query = text(f"""
            SELECT * FROM {table_name}
            ORDER BY {order_by} DESC
            LIMIT :limit
        """)
        
        result = db.execute(query, {"limit": limit})
        rows = result.fetchall()
        
        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for col_name, value in zip(columns, row):
                row_dict[col_name] = serialize_value(value)
            data.append(row_dict)
        
        return data
    finally:
        db.close()


def fetch_user_specific_data(table_name: str, user_id: int) -> List[Dict]:
    """Fetch all data for a specific user_id"""
    db = SessionLocal()
    try:
        # Get column names
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        
        # Check if table has user_id column
        if 'user_id' not in columns:
            return []
        
        query = text(f"""
            SELECT * FROM {table_name}
            WHERE user_id = :user_id
        """)
        
        result = db.execute(query, {"user_id": user_id})
        rows = result.fetchall()
        
        # Convert to list of dicts
        data = []
        for row in rows:
            row_dict = {}
            for col_name, value in zip(columns, row):
                row_dict[col_name] = serialize_value(value)
            data.append(row_dict)
        
        return data
    finally:
        db.close()


def export_database_structure():
    """Main export function"""
    
    # Define table categories
    general_tables = ["recipes", "items", "recipe_ingredients"]
    user_specific_tables = [
        "users",
        "user_profiles", 
        "user_goals",
        "user_paths",
        "user_preferences",
        "meal_plans",
        "meal_logs",
        "user_inventory"
    ]
    
    export_data = {
        "export_timestamp": datetime.now().isoformat(),
        "database_info": {
            "total_tables": len(general_tables) + len(user_specific_tables),
            "general_tables": general_tables,
            "user_specific_tables": user_specific_tables
        },
        "tables": {}
    }
    
    print("Starting database export...")
    print("=" * 60)
    
    # Export general tables (latest 10 entries)
    print("\n📊 Exporting GENERAL TABLES (latest 10 entries)...")
    for table_name in general_tables:
        try:
            print(f"  → Fetching {table_name}...")
            structure = get_table_structure(table_name)
            data = fetch_general_table_data(table_name, limit=10)
            
            export_data["tables"][table_name] = {
                "structure": structure,
                "sample_data": data,
                "total_records_fetched": len(data),
                "data_type": "general - latest 10 entries"
            }
            print(f"    ✓ Exported {len(data)} records")
        except Exception as e:
            print(f"    ✗ Error: {str(e)}")
            export_data["tables"][table_name] = {
                "error": str(e)
            }
    
    # Export user-specific tables (user_id = 98)
    print(f"\n👤 Exporting USER-SPECIFIC TABLES (user_id = 98)...")
    for table_name in user_specific_tables:
        try:
            print(f"  → Fetching {table_name}...")
            structure = get_table_structure(table_name)
            
            if table_name == "users":
                # For users table, just get user 98
                db = SessionLocal()
                try:
                    result = db.execute(text("SELECT * FROM users WHERE id = :user_id"), {"user_id": 98})
                    row = result.fetchone()
                    if row:
                        inspector = inspect(engine)
                        columns = [col['name'] for col in inspector.get_columns(table_name)]
                        row_dict = {col_name: serialize_value(value) for col_name, value in zip(columns, row)}
                        data = [row_dict]
                    else:
                        data = []
                finally:
                    db.close()
            else:
                data = fetch_user_specific_data(table_name, user_id=98)
            
            export_data["tables"][table_name] = {
                "structure": structure,
                "sample_data": data,
                "total_records_fetched": len(data),
                "data_type": f"user-specific - user_id = 98"
            }
            print(f"    ✓ Exported {len(data)} records")
        except Exception as e:
            print(f"    ✗ Error: {str(e)}")
            export_data["tables"][table_name] = {
                "error": str(e)
            }
    
    # Save to JSON file
    output_file = f"database_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print(f"✅ Export completed successfully!")
    print(f"📁 File saved: {output_file}")
    print(f"📊 Total tables exported: {len(export_data['tables'])}")
    
    # Print summary
    print("\n📋 EXPORT SUMMARY:")
    for table_name, table_data in export_data["tables"].items():
        if "error" not in table_data:
            print(f"  • {table_name}: {table_data['total_records_fetched']} records")
        else:
            print(f"  • {table_name}: ERROR - {table_data['error']}")
    
    return output_file


if __name__ == "__main__":
    try:
        output_file = export_database_structure()
        print(f"\n✨ You can now use '{output_file}' to explain your database structure!")
    except Exception as e:
        print(f"\n❌ Export failed: {str(e)}")
        import traceback
        traceback.print_exc()