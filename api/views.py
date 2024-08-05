from django.shortcuts import render

# Create your views here.
from django.shortcuts import render
from pyvis.network import Network

def plot_view(request):
    net = Network(height='600px', width='100%', bgcolor='#222222', font_color='white')

    # Add nodes and edges
    net.add_node(1, label="Node 1", title="Go to URL 1", url="https://example.com/1")
    net.add_node(2, label="Node 2", title="Go to URL 2", url="https://example.com/2")
    net.add_edge(1, 2)

    # Generate the graph
    net.show_buttons(filter_=['physics'])  # Optional: shows physics control buttons
    net.show("templates/plotapp/graph.html")

    return render(request, 'plotapp/graph.html')