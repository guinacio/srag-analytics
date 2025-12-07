"""
Generate LangGraph workflow diagram showing parallel fan-out/fan-in pattern.
Uses matplotlib - no external graphviz binary required.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path


def create_workflow_diagram():
    """Create the LangGraph workflow diagram showing parallel execution."""
    
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'SRAG Analytics - LangGraph Workflow', 
            fontsize=16, fontweight='bold', ha='center', va='center',
            color='#1a1a2e')
    ax.text(7, 9.0, 'Fan-out/Fan-in Parallel Execution Pattern', 
            fontsize=12, ha='center', va='center', color='#4a4a6a')
    
    # Colors
    colors = {
        'start': '#2196f3',      # Blue
        'parallel': '#ff9800',    # Orange
        'fanin': '#4caf50',       # Green
        'sequential': '#9c27b0',  # Purple
        'end': '#f44336',         # Red
    }
    
    # Node positions (x, y, width, height)
    nodes = {
        'START': (7, 8, 1.5, 0.6, colors['start']),
        'calculate_metrics': (2.5, 6, 3, 1.2, colors['parallel']),
        'fetch_news': (7, 6, 3, 1.2, colors['parallel']),
        'generate_charts': (11.5, 6, 3, 1.2, colors['parallel']),
        'write_report': (7, 3.5, 3.5, 1.2, colors['fanin']),
        'create_audit': (7, 1.5, 3, 1, colors['sequential']),
        'END': (7, 0.3, 1.5, 0.6, colors['end']),
    }
    
    # Node labels with descriptions
    node_labels = {
        'START': 'START',
        'calculate_metrics': 'calculate_metrics\n━━━━━━━━━━━━━━━━━\n• Taxa de aumento\n• Taxa mortalidade\n• Taxa UTI\n• Taxa vacinação',
        'fetch_news': 'fetch_news\n━━━━━━━━━━━━━━━━━\n• Tavily Search API\n• Brazilian domains\n• Date extraction (LLM)',
        'generate_charts': 'generate_charts\n━━━━━━━━━━━━━━━━━\n• Daily cases (30d)\n• Monthly cases (12m)\n• Moving average',
        'write_report': 'write_report (Fan-in)\n━━━━━━━━━━━━━━━━━━━━━\n• GPT-4o synthesis\n• Metrics + News + Charts\n• PT-BR narrative',
        'create_audit': 'create_audit\n━━━━━━━━━━━━━━━━━\n• Execution log\n• JSON audit trail',
        'END': 'END',
    }
    
    # Draw nodes
    for name, (x, y, w, h, color) in nodes.items():
        # Create rounded rectangle
        rect = FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.05,rounding_size=0.15",
            facecolor=color,
            edgecolor='#333333',
            linewidth=2,
            alpha=0.9
        )
        ax.add_patch(rect)
        
        # Add text
        fontsize = 7 if '\n' in node_labels[name] else 10
        ax.text(x, y, node_labels[name], 
                fontsize=fontsize, ha='center', va='center',
                color='white', fontweight='bold')
    
    # Draw arrows
    arrow_style = "Simple, tail_width=0.5, head_width=4, head_length=6"
    
    # Fan-out arrows (START to parallel nodes)
    fanout_arrows = [
        ((7, 7.7), (2.5, 6.6)),   # START -> calculate_metrics
        ((7, 7.7), (7, 6.6)),     # START -> fetch_news
        ((7, 7.7), (11.5, 6.6)),  # START -> generate_charts
    ]
    
    for start, end in fanout_arrows:
        arrow = FancyArrowPatch(
            start, end,
            arrowstyle=arrow_style,
            color=colors['start'],
            linewidth=2,
            mutation_scale=1,
            connectionstyle="arc3,rad=0"
        )
        ax.add_patch(arrow)
    
    # Fan-in arrows (parallel nodes to write_report)
    fanin_arrows = [
        ((2.5, 5.4), (5.8, 4.1)),   # calculate_metrics -> write_report
        ((7, 5.4), (7, 4.1)),       # fetch_news -> write_report
        ((11.5, 5.4), (8.2, 4.1)),  # generate_charts -> write_report
    ]
    
    for start, end in fanin_arrows:
        arrow = FancyArrowPatch(
            start, end,
            arrowstyle=arrow_style,
            color=colors['fanin'],
            linewidth=2,
            mutation_scale=1,
            connectionstyle="arc3,rad=0"
        )
        ax.add_patch(arrow)
    
    # Sequential arrows
    sequential_arrows = [
        ((7, 2.9), (7, 2.0)),   # write_report -> create_audit
        ((7, 1.0), (7, 0.6)),   # create_audit -> END
    ]
    
    for start, end in sequential_arrows:
        arrow = FancyArrowPatch(
            start, end,
            arrowstyle=arrow_style,
            color=colors['sequential'],
            linewidth=2,
            mutation_scale=1,
        )
        ax.add_patch(arrow)
    
    # Add "PARALLEL" label
    ax.text(7, 7.2, '⚡ PARALLEL EXECUTION ⚡', 
            fontsize=11, ha='center', va='center',
            color='#ff9800', fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='#fff3e0', edgecolor='#ff9800', alpha=0.8))
    
    # Add legend
    legend_elements = [
        mpatches.Patch(color=colors['start'], label='Entry Point'),
        mpatches.Patch(color=colors['parallel'], label='Parallel Nodes (Fan-out)'),
        mpatches.Patch(color=colors['fanin'], label='Sync Point (Fan-in)'),
        mpatches.Patch(color=colors['sequential'], label='Sequential Node'),
        mpatches.Patch(color=colors['end'], label='Exit Point'),
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9)
    
    # Add performance note
    perf_text = """Performance Benefit:
Sequential: T1 + T2 + T3 (e.g., 9s)
Parallel: max(T1, T2, T3) (e.g., 3s)
≈ 3x faster data gathering!"""
    
    ax.text(0.5, 2.5, perf_text, 
            fontsize=9, ha='left', va='top',
            fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#e3f2fd', edgecolor='#2196f3', alpha=0.8))
    
    plt.tight_layout()
    return fig


def main():
    """Generate and save workflow diagram."""
    output_dir = Path(__file__).parent
    output_path = output_dir / "workflow_graph.png"
    
    try:
        fig = create_workflow_diagram()
        fig.savefig(output_path, dpi=150, bbox_inches='tight', 
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        print(f"✅ Workflow diagram generated successfully!")
        print(f"   PNG: {output_path}")
    except Exception as e:
        print(f"❌ Error generating diagram: {e}")


if __name__ == "__main__":
    main()

