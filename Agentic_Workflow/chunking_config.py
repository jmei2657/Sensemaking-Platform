"""
Chunking Configuration for RAG System
This file contains configurable parameters for different chunking strategies.
"""

# ── General Chunking Parameters ─────────────────────────────────
CHUNKING_CONFIG = {
    # Default chunking strategy
    "default_strategy": "sentences",
    
    # Available strategies
    "strategies": ["sentences", "words", "paragraphs", "none"],
    
    # Sentence-based chunking
    "sentences": {
        "max_chunk_size": 512,  # characters
        "overlap": 50,          # characters
        "min_chunk_size": 50    # minimum chunk size
    },
    
    # Word-based chunking
    "words": {
        "max_words": 100,
        "overlap_words": 10,
        "min_words": 10
    },
    
    # Paragraph-based chunking
    "paragraphs": {
        "max_chunk_size": 512,  # characters
        "min_chunk_size": 50    # minimum chunk size
    }
}

# ── Content-Specific Configurations ─────────────────────────────
CONTENT_CONFIG = {
    "news": {
        "default_strategy": "sentences",
        "max_chunk_size": 512,
        "overlap": 50,
        "include_title_in_chunks": True,
        "title_weight": 1.5  # Give more weight to title content
    },
    
    "reddit": {
        "default_strategy": "sentences",
        "max_chunk_size": 768,  # Reddit posts can be longer
        "overlap": 75,
        "include_title_in_chunks": True,
        "title_weight": 1.2
    },
    
    "tmz": {
        "default_strategy": "sentences",
        "max_chunk_size": 600,  # TMZ articles are typically entertainment-focused
        "overlap": 60,
        "include_title_in_chunks": True,
        "title_weight": 1.4  # Entertainment news titles are important
    },
    
    "guardian": {
        "default_strategy": "paragraphs",  # Guardian articles are longer, more structured
        "max_chunk_size": 1024,  # Longer chunks for comprehensive articles
        "overlap": 100,
        "include_title_in_chunks": True,
        "title_weight": 1.3  # Quality journalism titles
    },
    
    "articles": {
        "default_strategy": "paragraphs",
        "max_chunk_size": 1024,
        "overlap": 100,
        "include_title_in_chunks": True,
        "title_weight": 1.3
    },
    
    "social_media": {
        "default_strategy": "words",
        "max_words": 80,
        "overlap_words": 8,
        "include_title_in_chunks": True,
        "title_weight": 1.1
    }
}

# ── Text Preprocessing Configuration ─────────────────────────────
PREPROCESSING_CONFIG = {
    "remove_special_chars": True,
    "normalize_whitespace": True,
    "remove_urls": False,
    "remove_emails": False,
    "lowercase": False,  # Keep case for better semantic understanding
    "remove_numbers": False,
    "min_text_length": 10
}

# ── Metadata Configuration ──────────────────────────────────────
METADATA_CONFIG = {
    "include_chunk_info": True,
    "include_strategy_info": True,
    "include_content_type": True,
    "include_original_id": True,
    "include_timestamp": False,
    "include_length": True
}

# ── Search Configuration ─────────────────────────────────────────
SEARCH_CONFIG = {
    "default_top_k": 5,
    "max_top_k": 20,
    "include_chunk_context": True,
    "show_chunk_metadata": True,
    "result_format": "detailed"  # "simple" or "detailed"
}

def get_chunking_params(content_type: str, strategy: str = None) -> dict:
    """Get chunking parameters for a specific content type and strategy."""
    content_config = CONTENT_CONFIG.get(content_type, CONTENT_CONFIG["news"])
    strategy = strategy or content_config.get("default_strategy", "sentences")
    
    base_params = CHUNKING_CONFIG[strategy].copy()
    base_params.update(content_config)
    
    return base_params

def get_preprocessing_config() -> dict:
    """Get text preprocessing configuration."""
    return PREPROCESSING_CONFIG.copy()

def get_metadata_config() -> dict:
    """Get metadata configuration."""
    return METADATA_CONFIG.copy()

def get_search_config() -> dict:
    """Get search configuration."""
    return SEARCH_CONFIG.copy() 