
from typing import Dict, List, Any
import re

def tokenize(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())

def create_inverted_index(data: Dict[str, Any], parent_key: str = '') -> Dict[str, List[str]]:
    index = {}
    
    def process_value(value: Any, current_key: str):
        if isinstance(value, dict):
            for k, v in value.items():
                new_key = f"{current_key}.{k}" if current_key else k
                process_value(v, new_key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                new_key = f"{current_key}[{i}]"
                process_value(item, new_key)
        else:
            tokens = tokenize(str(value))
            for token in tokens:
                if token not in index:
                    index[token] = []
                if current_key not in index[token]:
                    index[token].append(current_key)
    
    process_value(data, parent_key)
    return index

def search_fhir_data(data: Dict[str, Any], query: str, index: Dict[str, List[str]]) -> Dict[str, Any]:
    query_tokens = tokenize(query)
    relevant_paths = set()
    
    for token in query_tokens:
        if token in index:
            relevant_paths.update(index[token])
    
    result = {}
    
    def get_value_from_path(data: Dict[str, Any], path: str) -> Any:
        current = data
        parts = path.replace(']', '').split('.')
        
        for part in parts:
            if '[' in part:
                key, idx = part.split('[')
                current = current[key][int(idx)]
            else:
                current = current[part]
        return current
    
    for path in relevant_paths:
        try:
            value = get_value_from_path(data, path)
            current = result
            parts = path.split('.')
            
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[parts[-1]] = value
        except (KeyError, IndexError):
            continue
    
    return result
