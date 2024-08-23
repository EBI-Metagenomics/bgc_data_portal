import plotly.graph_objs as go
from plotly.subplots import make_subplots
from collections import Counter
from plotly.offline import plot

def generate_multibar_plot_html(counter_list, titles):
    """
    Generate a Plotly plot with multiple barplot subplots from a list of Counter objects.
    
    Args:
    - counter_list: List of Counter objects
    - titles: List of titles for each subplot
    
    Returns:
    - HTML string of the plot
    """
    # Number of subplots needed
    num_subplots = len(counter_list)
    
    # Create subplots: 1 row, multiple columns
    fig = make_subplots(rows=1, cols=num_subplots, subplot_titles=titles)
    
    # Add bar plots for each Counter object
    for i, counter in enumerate(counter_list):
        x_values = list(counter.keys())
        y_values = list(counter.values())
        
        fig.add_trace(
            go.Bar(
                x=x_values,
                y=y_values,
                name=titles[i],
                hoverinfo='x+y',  # Show both x (category) and y (count) on hover
                text=y_values,
                textposition='auto'  # Display the number of elements inside the bars
            ),
            row=1, col=i+1
        )
    
    # Update layout to make sure all subplots are displayed correctly
    fig.update_layout(
        height=400,  # Adjust height as necessary
        width=300*num_subplots,  # Adjust width based on the number of subplots
        title_text="Multiple Barplot Subplots",
        showlegend=False,
    )
    
    # Generate the HTML for the plot
    plot_html = plot(fig, output_type='div')
    
    return plot_html
