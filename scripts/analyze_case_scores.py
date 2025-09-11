#!/usr/bin/env python3

import os
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from argparse import ArgumentParser
from pathlib import Path
import numpy as np
import json


class CaseScoreAnalyzer:
    def __init__(self, case_id: int):
        self.case_id = case_id
        self.df = None
        
    @classmethod
    def parameters(cls):
        parser = ArgumentParser(description="Analyze scoring results for a specific case")
        parser.add_argument("--case", type=int, required=True, help="Case ID to analyze")
        parser.add_argument("--output-dir", type=Path, default=Path("analysis_outputs"), 
                          help="Directory to save plots and reports")
        return parser.parse_args()
    
    def load_data(self) -> pd.DataFrame:
        """Load scoring data for the specified case from the database."""
        query = f"""
        SELECT s.id as score_id, s.rubric_id, s.generated_note_id, s.overall_score, 
               gn.case_id, gn.text_llm_vendor as note_vendor, gn.text_llm_name as note_model,
               s.created, s.text_llm_vendor as scoring_vendor, s.scoring_result,
               r.rubric as rubric_json
        FROM score s 
        JOIN generated_note gn ON s.generated_note_id = gn.id 
        JOIN rubric r ON s.rubric_id = r.id
        WHERE gn.case_id = {self.case_id}
        AND s.id >= 3994
        ORDER BY s.created DESC
        """
        
        # Execute query and save to CSV
        cmd = f'source local_env.sh && psql $DATABASE_URL -c "\\copy ({query}) TO STDOUT WITH CSV HEADER"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Database query failed: {result.stderr}")
        
        # Parse CSV data
        from io import StringIO
        df = pd.read_csv(StringIO(result.stdout))
        
        # Clean up vendor names for consistency
        df['note_vendor_clean'] = df['note_vendor'].str.title()
        df['model_short'] = df['note_model'].apply(self._shorten_model_name)
        
        # Calculate max possible scores from rubric JSON
        df['max_possible_score'] = df['rubric_json'].apply(self._calculate_max_score)
        
        # Calculate normalized scores (as percentages)
        df['normalized_score'] = (df['overall_score'] / df['max_possible_score']) * 100
        
        self.df = df
        return df
    
    @staticmethod
    def _shorten_model_name(model: str) -> str:
        """Shorten model names for display."""
        if 'gpt-4o' in model.lower():
            return 'GPT-4o'
        elif 'claude' in model.lower():
            return 'Claude'
        return model
    
    @staticmethod
    def _calculate_max_score(rubric_json_str: str) -> float:
        """Calculate the maximum possible score from a rubric JSON string."""
        try:
            rubric = json.loads(rubric_json_str)
            return sum(criterion.get('weight', 0) for criterion in rubric)
        except (json.JSONDecodeError, TypeError, KeyError):
            return np.nan
    
    def generate_report(self) -> str:
        """Generate a text report with key statistics."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        report = []
        report.append(f"=== CASE {self.case_id} SCORING ANALYSIS ===\\n")
        
        # Basic stats
        total_scores = len(self.df)
        unique_notes = self.df['generated_note_id'].nunique()
        unique_rubrics = self.df['rubric_id'].nunique()
        
        report.append(f"Total Scores: {total_scores}")
        report.append(f"Unique Notes: {unique_notes}")
        report.append(f"Unique Rubrics: {unique_rubrics}")
        report.append(f"Expected Scores (notes × rubrics × 2): {unique_notes * unique_rubrics * 2}\\n")
        
        # Vendor comparison - Raw scores
        vendor_stats_raw = self.df.groupby('note_vendor_clean')['overall_score'].agg([
            'count', 'mean', 'std', 'min', 'max', 'median'
        ]).round(2)
        
        # Vendor comparison - Normalized scores (percentages)
        vendor_stats_norm = self.df.groupby('note_vendor_clean')['normalized_score'].agg([
            'mean', 'std', 'min', 'max', 'median'
        ]).round(2)
        
        # Max possible scores by rubric
        rubric_max_scores = self.df.groupby('rubric_id')['max_possible_score'].first().round(0)
        
        report.append("=== VENDOR COMPARISON (Raw Scores) ===")
        report.append(vendor_stats_raw.to_string())
        report.append("")
        
        report.append("=== VENDOR COMPARISON (Normalized %) ===")
        report.append(vendor_stats_norm.to_string())
        report.append("")
        
        report.append("=== RUBRIC MAX POSSIBLE SCORES ===")
        for rubric_id, max_score in rubric_max_scores.items():
            report.append(f"Rubric {rubric_id}: {max_score} points")
        report.append("")
        
        # Note-level analysis - Raw scores
        note_stats_raw = self.df.groupby(['generated_note_id', 'note_vendor_clean', 'model_short'])['overall_score'].agg([
            'count', 'mean', 'std', 'min', 'max'
        ]).round(2)
        
        # Note-level analysis - Normalized scores
        note_stats_norm = self.df.groupby(['generated_note_id', 'note_vendor_clean', 'model_short'])['normalized_score'].agg([
            'mean', 'std', 'min', 'max'
        ]).round(2)
        
        report.append("=== NOTE-LEVEL ANALYSIS (Raw Scores) ===")
        report.append(note_stats_raw.to_string())
        report.append("")
        
        report.append("=== NOTE-LEVEL ANALYSIS (Normalized %) ===")
        report.append(note_stats_norm.to_string())
        report.append("")
        
        # Rubric-level analysis - Raw scores
        rubric_stats_raw = self.df.groupby('rubric_id')['overall_score'].agg([
            'count', 'mean', 'std', 'min', 'max'
        ]).round(2)
        
        # Rubric-level analysis - Normalized scores
        rubric_stats_norm = self.df.groupby('rubric_id')['normalized_score'].agg([
            'mean', 'std', 'min', 'max'
        ]).round(2)
        
        report.append("=== RUBRIC-LEVEL ANALYSIS (Raw Scores) ===")
        report.append(rubric_stats_raw.to_string())
        report.append("")
        
        report.append("=== RUBRIC-LEVEL ANALYSIS (Normalized %) ===")
        report.append(rubric_stats_norm.to_string())
        
        return "\\n".join(report)
    
    def create_distribution_plot(self, output_path: Path) -> None:
        """Create distribution plots comparing vendors and notes."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        # Set up the plot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f'Case {self.case_id} Scoring Analysis', fontsize=16, fontweight='bold')
        
        # Color palettes
        vendor_colors = {'Anthropic': '#FF6B6B', 'Openai': '#4ECDC4'}
        note_colors = plt.cm.Set3(np.linspace(0, 1, self.df['generated_note_id'].nunique()))
        
        # 1. Overall distribution by vendor (normalized)
        sns.boxplot(data=self.df, x='note_vendor_clean', y='normalized_score', 
                   hue='note_vendor_clean', palette=vendor_colors, ax=ax1, legend=False)
        ax1.set_title('Normalized Score Distribution by Vendor (%)')
        ax1.set_xlabel('Vendor')
        ax1.set_ylabel('Normalized Score (%)')
        ax1.set_ylim(0, 100)
        
        # Add count annotations
        for i, vendor in enumerate(self.df['note_vendor_clean'].unique()):
            count = len(self.df[self.df['note_vendor_clean'] == vendor])
            ax1.text(i, ax1.get_ylim()[1]*0.95, f'n={count}', ha='center', fontweight='bold')
        
        # 2. Histogram by vendor (normalized)
        for vendor in self.df['note_vendor_clean'].unique():
            vendor_data = self.df[self.df['note_vendor_clean'] == vendor]['normalized_score']
            ax2.hist(vendor_data, alpha=0.7, label=vendor, bins=15, 
                    color=vendor_colors.get(vendor, 'gray'))
        ax2.set_title('Normalized Score Histogram by Vendor')
        ax2.set_xlabel('Normalized Score (%)')
        ax2.set_ylabel('Frequency')
        ax2.set_xlim(0, 100)
        ax2.legend()
        
        # 3. Individual note performance (normalized)
        note_means = self.df.groupby(['generated_note_id', 'note_vendor_clean', 'model_short'])['normalized_score'].mean().reset_index()
        
        # Create scatter plot for individual notes
        labeled_vendors = set()
        for i, (note_id, group) in enumerate(note_means.groupby('generated_note_id')):
            vendor = group['note_vendor_clean'].iloc[0]
            model = group['model_short'].iloc[0]
            score = group['normalized_score'].iloc[0]
            
            label = vendor if vendor not in labeled_vendors else ""
            if label:
                labeled_vendors.add(vendor)
                
            ax3.scatter(i, score, 
                       color=vendor_colors.get(vendor, 'gray'),
                       s=100, alpha=0.8, label=label)
            
            ax3.text(i, score + 2, f'{note_id}', ha='center', fontsize=8, rotation=45)
        
        ax3.set_title('Mean Normalized Score by Individual Note')
        ax3.set_xlabel('Note Index')
        ax3.set_ylabel('Mean Normalized Score (%)')
        ax3.set_ylim(0, 100)
        ax3.legend()
        
        # 4. Score range by note (normalized)
        note_ranges = self.df.groupby(['generated_note_id', 'note_vendor_clean'])['normalized_score'].agg(['min', 'max', 'mean']).reset_index()
        note_ranges['range'] = note_ranges['max'] - note_ranges['min']
        
        for vendor in note_ranges['note_vendor_clean'].unique():
            vendor_data = note_ranges[note_ranges['note_vendor_clean'] == vendor]
            ax4.scatter(vendor_data['mean'], vendor_data['range'], 
                       color=vendor_colors.get(vendor, 'gray'),
                       alpha=0.7, s=80, label=vendor)
        
        ax4.set_title('Score Consistency (Range vs Mean) - Normalized')
        ax4.set_xlabel('Mean Normalized Score (%)')
        ax4.set_ylabel('Score Range (Max - Min) (%)')
        ax4.set_xlim(0, 100)
        ax4.set_ylim(0, None)
        ax4.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
    
    def run_analysis(self, output_dir: Path) -> None:
        """Run complete analysis and save results."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Loading data for case {self.case_id}...")
        self.load_data()
        
        print(f"Generating report...")
        report = self.generate_report()
        
        # Save report
        report_path = output_dir / f"case_{self.case_id}_analysis.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"Creating distribution plots...")
        plot_path = output_dir / f"case_{self.case_id}_distribution.png"
        self.create_distribution_plot(plot_path)
        
        # Save data for further analysis
        data_path = output_dir / f"case_{self.case_id}_data.csv"
        self.df.to_csv(data_path, index=False)
        
        print(f"\\nAnalysis complete!")
        print(f"Report saved to: {report_path}")
        print(f"Plots saved to: {plot_path}")
        print(f"Data saved to: {data_path}")
        print(f"\\n{report}")
    
    @classmethod
    def run(cls) -> None:
        args = cls.parameters()
        analyzer = cls(args.case)
        analyzer.run_analysis(args.output_dir)


if __name__ == "__main__":
    CaseScoreAnalyzer.run()