"""
Call Graph - Code relationship graph builder
Simplified from FastCode's graph_builder.py for commit review
"""

import os
import pickle
import logging
import sys
from typing import Dict, List, Any, Set, Optional

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

try:
    from .elements import CodeElement
except ImportError:
    from elements import CodeElement


class CallGraphBuilder:
    """Build and query code relationship graphs"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Graphs
        if HAS_NETWORKX:
            self.call_graph = nx.DiGraph()
            self.dependency_graph = nx.DiGraph()
            self.inheritance_graph = nx.DiGraph()
        else:
            self.call_graph = None
            self.dependency_graph = None
            self.inheritance_graph = None
        
        # Maps for quick lookup
        self.element_by_name: Dict[str, CodeElement] = {}
        self.element_by_id: Dict[str, CodeElement] = {}
        self.imports_by_file: Dict[str, List[Dict]] = {}
        
        # Scope lookup for call graph optimization
        self.scope_lookup: Dict[tuple, str] = {}
        self.classes_by_name_lookup: Dict[str, List[CodeElement]] = {}
        
        # Persistence
        self.persist_dir = None
    
    def set_persist_dir(self, persist_dir: str):
        """Set directory for saving/loading graph data"""
        self.persist_dir = persist_dir
        if persist_dir and not os.path.exists(persist_dir):
            os.makedirs(persist_dir, exist_ok=True)
    
    def build_graphs(self, elements: List[CodeElement]):
        """
        Build all graphs from code elements
        
        Args:
            elements: List of code elements
        """
        if not HAS_NETWORKX:
            self.logger.warning("networkx not installed, graph features limited")
            return
            
        self.logger.info(f"Building code relationship graphs from {len(elements)} elements")
        
        # Index elements by name and id
        for elem in elements:
            self.element_by_name[elem.name] = elem
            self.element_by_id[elem.id] = elem
            
            # Populate scope lookup for call graph
            if elem.type in ["function", "method", "class"]:
                key = (elem.file_path, elem.type, elem.name)
                self.scope_lookup[key] = elem.id
            
            # Populate class lookup for inheritance
            if elem.type == "class":
                if elem.name not in self.classes_by_name_lookup:
                    self.classes_by_name_lookup[elem.name] = []
                self.classes_by_name_lookup[elem.name].append(elem)
            
            # Add nodes to graphs
            if elem.type == "file":
                self.dependency_graph.add_node(elem.id)
            
            if elem.type == "class":
                self.inheritance_graph.add_node(elem.id)
            
            if elem.type in ["function", "method", "class"]:
                self.call_graph.add_node(elem.id)
            
            # Track imports
            if elem.type == "file" and elem.metadata:
                imports = elem.metadata.get("imports", [])
                if imports:
                    self.imports_by_file[elem.file_path] = imports
        
        # Build call graph edges from element metadata
        for elem in elements:
            if elem.type in ["function", "method"] and elem.metadata:
                calls = elem.metadata.get("calls", [])
                for callee_name in calls:
                    callee_elem = self.element_by_name.get(callee_name)
                    if callee_elem:
                        self.call_graph.add_edge(elem.id, callee_elem.id)
        
        self.logger.info(
            f"Built graphs: call ({self.call_graph.number_of_nodes()} nodes), "
            f"dependency ({self.dependency_graph.number_of_nodes()} nodes), "
            f"inheritance ({self.inheritance_graph.number_of_nodes()} nodes)"
        )
    
    def add_call_edge(self, caller_id: str, callee_id: str):
        """Add a call relationship edge"""
        if HAS_NETWORKX and self.call_graph:
            self.call_graph.add_edge(caller_id, callee_id)
    
    def get_callers(self, element_id: str) -> List[str]:
        """
        Get functions that call this function
        
        Args:
            element_id: ID of the element
            
        Returns:
            List of element IDs that call this element
        """
        if HAS_NETWORKX and element_id in self.call_graph:
            return list(self.call_graph.predecessors(element_id))
        return []
    
    def get_callees(self, element_id: str) -> List[str]:
        """
        Get functions called by this function
        
        Args:
            element_id: ID of the element
            
        Returns:
            List of element IDs called by this element
        """
        if HAS_NETWORKX and element_id in self.call_graph:
            return list(self.call_graph.successors(element_id))
        return []
    
    def get_dependencies(self, element_id: str) -> List[str]:
        """Get elements this element depends on"""
        if HAS_NETWORKX and element_id in self.dependency_graph:
            return list(self.dependency_graph.successors(element_id))
        return []
    
    def get_dependents(self, element_id: str) -> List[str]:
        """Get elements that depend on this element"""
        if HAS_NETWORKX and element_id in self.dependency_graph:
            return list(self.dependency_graph.predecessors(element_id))
        return []
    
    def get_subclasses(self, element_id: str) -> List[str]:
        """Get subclasses of this class"""
        if HAS_NETWORKX and element_id in self.inheritance_graph:
            return list(self.inheritance_graph.successors(element_id))
        return []
    
    def get_superclasses(self, element_id: str) -> List[str]:
        """Get superclasses of this class"""
        if HAS_NETWORKX and element_id in self.inheritance_graph:
            return list(self.inheritance_graph.predecessors(element_id))
        return []
    
    def find_path(self, source_id: str, target_id: str, 
                  graph_type: str = "call") -> Optional[List[str]]:
        """
        Find path between two elements
        
        Args:
            source_id: Source element ID
            target_id: Target element ID
            graph_type: Type of graph (call, dependency, inheritance)
        
        Returns:
            List of element IDs forming the path, or None
        """
        if not HAS_NETWORKX:
            return None
            
        graph_map = {
            "call": self.call_graph,
            "dependency": self.dependency_graph,
            "inheritance": self.inheritance_graph,
        }
        
        graph = graph_map.get(graph_type)
        if graph is None:
            return None
        
        try:
            return nx.shortest_path(graph, source_id, target_id)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None
    
    def get_related_elements(self, element_id: str, max_hops: int = 2) -> Set[str]:
        """
        Get related elements within N hops
        
        Args:
            element_id: Starting element ID
            max_hops: Maximum number of hops
        
        Returns:
            Set of related element IDs
        """
        if not HAS_NETWORKX or not self.call_graph:
            return set()
            
        if element_id not in self.call_graph:
            return set()
        
        related = set()
        queue = [(element_id, 0)]
        visited = {element_id}
        
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            
            # Get callers and callees
            for neighbor in self.call_graph.predecessors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    related.add(neighbor)
                    queue.append((neighbor, depth + 1))
            
            for neighbor in self.call_graph.successors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    related.add(neighbor)
                    queue.append((neighbor, depth + 1))
        
        return related
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the graphs"""
        if not HAS_NETWORKX:
            return {}
            
        return {
            "call_graph": {
                "nodes": self.call_graph.number_of_nodes(),
                "edges": self.call_graph.number_of_edges(),
            },
            "dependency_graph": {
                "nodes": self.dependency_graph.number_of_nodes(),
                "edges": self.dependency_graph.number_of_edges(),
            },
            "inheritance_graph": {
                "nodes": self.inheritance_graph.number_of_nodes(),
                "edges": self.inheritance_graph.number_of_edges(),
            },
        }
    
    def save(self, name: str = "graph"):
        """Save graphs to disk"""
        if not self.persist_dir:
            self.logger.warning("No persist_dir set, cannot save")
            return
        
        try:
            data = {
                "element_by_name": self.element_by_name,
                "element_by_id": self.element_by_id,
                "imports_by_file": self.imports_by_file,
                "scope_lookup": self.scope_lookup,
                "classes_by_name_lookup": self.classes_by_name_lookup,
            }
            
            # Save elements without embeddings
            elements_data = []
            for elem in self.element_by_id.values():
                elem_dict = elem.to_dict()
                if "embedding" in elem_dict:
                    del elem_dict["embedding"]
                elements_data.append(elem_dict)
            
            graph_path = os.path.join(self.persist_dir, f"{name}_call_graph.pkl")
            with open(graph_path, 'wb') as f:
                pickle.dump({
                    "elements": elements_data,
                    "metadata": data,
                }, f)
            
            self.logger.info(f"Saved call graph to {graph_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save graph: {e}")
    
    def load(self, name: str = "graph") -> bool:
        """Load graphs from disk"""
        if not self.persist_dir:
            self.logger.warning("No persist_dir set, cannot load")
            return False
        
        graph_path = os.path.join(self.persist_dir, f"{name}_call_graph.pkl")
        if not os.path.exists(graph_path):
            self.logger.warning(f"Graph file not found: {graph_path}")
            return False
        
        try:
            with open(graph_path, 'rb') as f:
                data = pickle.load(f)
            
            elements_data = data.get("elements", [])
            metadata = data.get("metadata", {})
            
            # Reconstruct CodeElement objects
            for elem_dict in elements_data:
                elem = CodeElement(**elem_dict)
                self.element_by_id[elem.id] = elem
                self.element_by_name[elem.name] = elem
            
            # Restore metadata
            self.imports_by_file = metadata.get("imports_by_file", {})
            self.scope_lookup = metadata.get("scope_lookup", {})
            self.classes_by_name_lookup = metadata.get("classes_by_name_lookup", {})
            
            # Rebuild graphs from elements
            self.build_graphs(list(self.element_by_id.values()))
            
            self.logger.info(f"Loaded call graph from {graph_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load graph: {e}")
            return False
