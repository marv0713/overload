import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def generate_infographic(chart_data_json: str, output_path: str) -> bool:
    """
    Parses the JSON chart data and generates a beautiful matplotlib infographic.
    chart_data_json expected format:
    {
        "title": "核心数据一览",
        "metrics": [
            {"name": "营收增速", "value": 49, "suffix": "%"},
            {"name": "利润率下降", "value": -6, "suffix": "%"}
        ]
    }
    """
    try:
        data = json.loads(chart_data_json)
        metrics = data.get("metrics", [])
        if not metrics:
            return False

        # Set style for "marv 的炼金术" (dark/hacker theme)
        plt.style.use('dark_background')
        sns.set_theme(style="darkgrid", rc={"axes.facecolor": "#121212", "figure.facecolor": "#121212", "text.color": "#e0e0e0"})

        # To support Chinese fonts, we need to set the font properties.
        # macOS commonly has 'PingFang SC' or 'Arial Unicode MS'
        plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Arial Unicode MS', 'Heiti TC', 'SimHei']
        plt.rcParams['axes.unicode_minus'] = False

        fig, ax = plt.subplots(figsize=(8, 4 + len(metrics) * 0.5))

        names = [m["name"] for m in metrics]
        values = [float(m["value"]) for m in metrics]
        suffixes = [m.get("suffix", "") for m in metrics]

        # Colors: Green for positive, Red for negative (typical in finance)
        colors = ['#28a745' if v > 0 else '#dc3545' for v in values]

        bars = ax.barh(names, values, color=colors, alpha=0.8)

        # Add values at the end of the bars
        for bar, suffix in zip(bars, suffixes):
            width = bar.get_width()
            label_x_pos = width + 1 if width > 0 else width - 1
            ha = 'left' if width > 0 else 'right'
            ax.text(label_x_pos, bar.get_y() + bar.get_height()/2,
                    f'{width:g}{suffix}',
                    ha=ha, va='center', color='white', fontweight='bold', fontsize=12)

        ax.set_title(data.get("title", "核心数据提炼"), fontsize=16, fontweight='bold', pad=20, color="#d4af37") # Gold color for alchemy

        # Add watermark
        fig.text(0.95, 0.05, '@marv 的炼金术',
                 fontsize=14, color='gray', ha='right', va='bottom', alpha=0.5)

        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='#121212')
        plt.close()
        return True
    except Exception as e:
        print(f"Failed to generate infographic: {e}")
        return False
