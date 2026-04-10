from django.core.exceptions import ValidationError
from .schemas import CATEGORY_SCHEMAS

class AttributeValidator:
    """Ensures dynamic attributes match the category schema."""
    
    @staticmethod
    def validate(category_name, attributes):
        if not category_name:
            return attributes
            
        schema = CATEGORY_SCHEMAS.get(category_name.lower())
        if schema is None:
            # If category not in schema, we might list it as an error or allow all
            # For strictness:
            # raise ValidationError(f"No attribute schema for category '{category_name}'")
            return attributes

        # Check for invalid fields
        invalid_fields = [f for f in attributes.keys() if f not in schema]
        if invalid_fields:
            raise ValidationError(
                f"Invalid fields for category '{category_name}': {', '.join(invalid_fields)}"
            )
            
        return attributes

def validate_listing_attributes(category, attributes):
    """Wrapper for attribute validation."""
    if hasattr(category, 'name'):
        category_name = category.name
    else:
        # Might be an ID or string
        category_name = str(category)
        
    return AttributeValidator.validate(category_name, attributes)
