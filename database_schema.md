# TuWebFacil - Supabase Database Schema

## Tables Structure

### 1. clients
Stores basic client information.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| name | text | Client's name |
| phone | text | Client's WhatsApp phone number (unique) |
| email | text | Client's email address |
| instagram_handle | text | Client's Instagram handle |
| business_type | text | Type of business/industry |
| status | text | Client status (lead, active, inactive, etc.) |
| notes | text | Additional notes about the client |

### 2. subscriptions
Manages client subscription information.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| plan_type | text | Subscription plan type (basic, premium, etc.) |
| status | text | Subscription status (active, canceled, pending) |
| start_date | timestamp | Subscription start date |
| end_date | timestamp | Subscription end date |
| price | numeric | Subscription price |
| auto_renew | boolean | Whether subscription auto-renews |
| mercadopago_subscription_id | text | MercadoPago subscription ID |
| last_payment_date | timestamp | Date of last payment |
| next_payment_date | timestamp | Date of next payment |

### 3. websites
Stores information about client websites.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| domain | text | Website domain (if custom domain is used) |
| subdomain | text | TuWebFacil subdomain |
| template_id | text | ID of the template used |
| status | text | Website status (draft, published, archived) |
| last_updated | timestamp | Last update timestamp |
| seo_title | text | SEO title |
| seo_description | text | SEO description |
| analytics_id | text | Google Analytics ID (if applicable) |

### 4. website_content
Stores the actual content of websites in JSON format.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| website_id | uuid | Foreign key to websites table |
| version | integer | Content version number |
| is_current | boolean | Whether this is the current version |
| content | jsonb | Website content in JSON format |
| content_type | text | Type of content (page, blog, gallery, etc.) |
| path | text | URL path for this content |
| metadata | jsonb | Additional metadata |

### 5. content_history
Tracks changes to website content for the "undo" functionality.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| website_content_id | uuid | Foreign key to website_content table |
| previous_content | jsonb | Previous content state |
| change_description | text | Description of changes made |
| changed_by | text | Who made the change (client, system, admin) |
| can_revert | boolean | Whether this change can be reverted |

### 6. payments
Records payment transactions.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| subscription_id | uuid | Foreign key to subscriptions table |
| amount | numeric | Payment amount |
| currency | text | Payment currency |
| status | text | Payment status (successful, failed, pending) |
| payment_method | text | Payment method used |
| mercadopago_payment_id | text | MercadoPago payment ID |
| invoice_number | text | Invoice number |
| payment_date | timestamp | Date of payment |
| metadata | jsonb | Additional payment metadata |

### 7. marketing_content
Stores generated marketing content for Instagram.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| content_type | text | Type of content (post, story, reel) |
| copy_text | text | Generated copy text |
| design_description | text | Description of design |
| status | text | Content status (draft, approved, published) |
| scheduled_date | timestamp | Date scheduled for publishing |
| published_date | timestamp | Date actually published |
| performance_metrics | jsonb | Metrics after publishing |
| instagram_post_id | text | ID of the post on Instagram (if published) |

### 8. competitor_analysis
Stores analysis of competitors.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| competitor_name | text | Name of competitor |
| competitor_instagram | text | Competitor's Instagram handle |
| competitor_website | text | Competitor's website URL |
| analysis_data | jsonb | Analysis data in JSON format |
| strengths | text[] | Array of competitor strengths |
| weaknesses | text[] | Array of competitor weaknesses |
| opportunities | text[] | Opportunities identified |
| last_analyzed | timestamp | Date of last analysis |

### 9. whatsapp_interactions
Tracks WhatsApp interactions for the UX flow.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| client_id | uuid | Foreign key to clients table |
| message | text | Message content |
| direction | text | Direction (incoming, outgoing) |
| context | text | Current context of conversation |
| intent | text | Detected intent of message |
| current_state | text | Current state in the UX flow |
| previous_state | text | Previous state in the UX flow |
| action_taken | text | Action taken based on message |
| metadata | jsonb | Additional metadata |

### 10. templates
Stores website templates.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp (auto-generated) |
| name | text | Template name |
| description | text | Template description |
| category | text | Template category |
| base_html | text | Base HTML structure |
| base_css | text | Base CSS styles |
| base_js | text | Base JavaScript |
| screenshot_url | text | URL to template screenshot |
| is_active | boolean | Whether template is active |
| metadata | jsonb | Additional template metadata |

## Content JSON Structure Examples

### Website Content JSON (for website_content.content)

```json
{
  "header": {
    "logo": "https://storage.url/logo.png",
    "title": "Business Name",
    "tagline": "Your catchy tagline here",
    "menu": [
      {"label": "Home", "url": "/"},
      {"label": "Services", "url": "/services"},
      {"label": "Gallery", "url": "/gallery"},
      {"label": "Contact", "url": "/contact"}
    ]
  },
  "hero": {
    "title": "Welcome to Our Business",
    "subtitle": "We provide the best services in town",
    "background_image": "https://storage.url/hero.jpg",
    "cta_button": {
      "text": "Contact Us",
      "url": "/contact"
    }
  },
  "sections": [
    {
      "type": "about",
      "title": "About Us",
      "content": "Lorem ipsum dolor sit amet...",
      "image": "https://storage.url/about.jpg"
    },
    {
      "type": "services",
      "title": "Our Services",
      "items": [
        {
          "title": "Service 1",
          "description": "Description of service 1",
          "icon": "icon-service-1",
          "image": "https://storage.url/service1.jpg"
        },
        {
          "title": "Service 2",
          "description": "Description of service 2",
          "icon": "icon-service-2",
          "image": "https://storage.url/service2.jpg"
        }
      ]
    },
    {
      "type": "gallery",
      "title": "Our Work",
      "images": [
        {
          "url": "https://storage.url/gallery1.jpg",
          "caption": "Project 1",
          "alt": "Image of Project 1"
        },
        {
          "url": "https://storage.url/gallery2.jpg",
          "caption": "Project 2",
          "alt": "Image of Project 2"
        }
      ]
    },
    {
      "type": "testimonials",
      "title": "What Our Clients Say",
      "items": [
        {
          "quote": "Great service!",
          "author": "John Doe",
          "position": "CEO, Company X"
        },
        {
          "quote": "Highly recommended!",
          "author": "Jane Smith",
          "position": "Marketing Director, Company Y"
        }
      ]
    },
    {
      "type": "pricing",
      "title": "Our Pricing",
      "items": [
        {
          "name": "Basic Plan",
          "price": "$99",
          "period": "monthly",
          "features": ["Feature 1", "Feature 2", "Feature 3"],
          "cta": {
            "text": "Get Started",
            "url": "/contact"
          }
        },
        {
          "name": "Premium Plan",
          "price": "$199",
          "period": "monthly",
          "features": ["Feature 1", "Feature 2", "Feature 3", "Feature 4", "Feature 5"],
          "cta": {
            "text": "Get Started",
            "url": "/contact"
          }
        }
      ]
    }
  ],
  "footer": {
    "copyright": "© 2026 Business Name. All rights reserved.",
    "social_links": [
      {"platform": "facebook", "url": "https://facebook.com/business"},
      {"platform": "instagram", "url": "https://instagram.com/business"},
      {"platform": "twitter", "url": "https://twitter.com/business"}
    ],
    "contact_info": {
      "email": "info@business.com",
      "phone": "+1234567890",
      "address": "123 Main St, City, Country"
    }
  },
  "seo": {
    "title": "Business Name | Your Tagline",
    "description": "Description for search engines",
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }
}
```

### Marketing Content JSON (for marketing_content.design_description)

```json
{
  "post_type": "carousel",
  "slides": [
    {
      "background_color": "#f5f5f5",
      "text_color": "#333333",
      "main_text": "5 TIPS TO IMPROVE YOUR WEBSITE",
      "font": "Montserrat Bold",
      "image_description": "Laptop with modern website design",
      "layout": "text_over_image"
    },
    {
      "background_color": "#ffffff",
      "text_color": "#333333",
      "main_text": "1. MOBILE OPTIMIZATION",
      "secondary_text": "Make sure your website looks great on all devices",
      "font": "Montserrat",
      "layout": "split_text_image",
      "image_position": "right"
    }
  ],
  "style_guide": {
    "brand_colors": ["#4a90e2", "#50e3c2", "#b8e986"],
    "fonts": ["Montserrat", "Open Sans"],
    "logo_position": "bottom_right",
    "visual_style": "minimalist"
  }
}
```

### Competitor Analysis JSON (for competitor_analysis.analysis_data)

```json
{
  "overview": {
    "name": "Competitor XYZ",
    "website": "https://competitor-xyz.com",
    "instagram": "@competitor_xyz",
    "followers": 12500,
    "engagement_rate": 3.2,
    "posting_frequency": "3 times per week"
  },
  "content_analysis": {
    "top_performing_posts": [
      {
        "url": "https://instagram.com/p/abc123",
        "likes": 1250,
        "comments": 45,
        "content_type": "tutorial",
        "topic": "website design tips"
      }
    ],
    "content_themes": ["web design", "SEO tips", "client showcases"],
    "visual_style": "bright, colorful, with consistent brand elements",
    "tone_of_voice": "professional but approachable"
  },
  "website_analysis": {
    "design_quality": 8,
    "mobile_responsiveness": 7,
    "loading_speed": 6,
    "key_features": ["portfolio showcase", "blog", "testimonials"],
    "call_to_actions": ["Free consultation", "Download guide"]
  },
  "swot": {
    "strengths": ["Strong visual identity", "High-quality portfolio"],
    "weaknesses": ["Slow website", "Inconsistent posting schedule"],
    "opportunities": ["No focus on local businesses", "Poor mobile experience"],
    "threats": ["Growing quickly", "Strong client testimonials"]
  },
  "recommendations": [
    "Focus on mobile optimization to outperform their weak mobile experience",
    "Maintain consistent posting schedule to build better audience engagement",
    "Highlight local business focus as a differentiator"
  ]
}
```

## Database Relationships

1. A client can have:
   - One or more subscriptions (one-to-many)
   - One or more websites (one-to-many)
   - Multiple marketing content entries (one-to-many)
   - Multiple competitor analyses (one-to-many)
   - Multiple WhatsApp interactions (one-to-many)
   - Multiple payments (one-to-many)

2. A website can have:
   - Multiple content entries (one-to-many)
   - Is based on one template (many-to-one)

3. A website content entry can have:
   - Multiple history entries for undo functionality (one-to-many)

4. A subscription can have:
   - Multiple payment records (one-to-many)

## Indexes and Performance Considerations

For optimal performance, the following indexes should be created:

1. clients:
   - phone (for quick lookups by WhatsApp number)
   - instagram_handle (for quick lookups by Instagram handle)

2. subscriptions:
   - client_id (for quick lookups of client subscriptions)
   - status (for filtering active/inactive subscriptions)
   - next_payment_date (for scheduling payment reminders)

3. website_content:
   - website_id + is_current (for quickly finding current content)
   - website_id + content_type + path (for URL routing)

4. whatsapp_interactions:
   - client_id + created_at (for retrieving recent conversations)
   - current_state (for state machine processing)

5. payments:
   - client_id + created_at (for payment history)
   - status (for filtering by payment status)
   - subscription_id (for subscription payment history)

## Security Rules

1. Row-Level Security (RLS) policies should be implemented to ensure:
   - Clients can only access their own data
   - Admin users can access all data
   - System processes have appropriate access levels

2. Sensitive payment information should be encrypted or stored securely according to PCI compliance standards.

3. API access should be restricted using appropriate authentication and authorization mechanisms.