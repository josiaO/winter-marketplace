# features/features_registry.py
"""
Central registry for all platform features.
All features should be defined here for consistency.
"""

FEATURES = [
    # Property Management Features
    {
        'code': 'PROPERTY_MANAGEMENT',
        'name': 'Property Management',
        'description': 'Ability to create, edit, and manage property listings',
        'is_active': True,
    },
    {
        'code': 'ADVANCED_SEARCH',
        'name': 'Advanced Property Search',
        'description': 'Access to advanced search filters and saved searches',
        'is_active': True,
    },
    {
        'code': 'PROPERTY_ANALYTICS',
        'name': 'Property Analytics',
        'description': 'View detailed analytics and statistics for your properties',
        'is_active': True,
    },
    {
        'code': 'BULK_UPLOAD',
        'name': 'Bulk Property Upload',
        'description': 'Upload multiple properties at once via CSV/Excel',
        'is_active': False,  # Coming soon
    },
    
    # Communication Features
    {
        'code': 'MESSAGING',
        'name': 'Direct Messaging',
        'description': 'Send and receive messages with agents and users',
        'is_active': True,
    },
    {
        'code': 'GROUP_CHAT',
        'name': 'Group Conversations',
        'description': 'Participate in group chats for property discussions',
        'is_active': False,  # Coming soon
    },
    {
        'code': 'VIDEO_CALLS',
        'name': 'Video Consultations',
        'description': 'Schedule and conduct video calls with agents',
        'is_active': False,  # Coming soon
    },
    
    # Premium Features
    {
        'code': 'FEATURED_LISTINGS',
        'name': 'Featured Listings',
        'description': 'Promote your properties with featured placement',
        'is_active': True,
    },
    {
        'code': 'VIRTUAL_TOURS',
        'name': 'Virtual Property Tours',
        'description': 'Create and share 360° virtual property tours',
        'is_active': True,
    },
    {
        'code': 'PRIORITY_SUPPORT',
        'name': 'Priority Support',
        'description': 'Get priority assistance from our support team',
        'is_active': True,
    },
    
    # Agent Tools
    {
        'code': 'LEAD_MANAGEMENT',
        'name': 'Lead Management',
        'description': 'Track and manage property leads and inquiries',
        'is_active': True,
    },
    {
        'code': 'AUTOMATED_REPORTS',
        'name': 'Automated Reports',
        'description': 'Receive automated performance reports',
        'is_active': True,
    },
    {
        'code': 'CLIENT_PORTAL',
        'name': 'Client Portal',
        'description': 'Dedicated portal for clients to view shortlisted properties',
        'is_active': False,  # Coming soon
    },
]
