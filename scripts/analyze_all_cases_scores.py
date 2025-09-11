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


class AllCasesScoreAnalyzer:
    def __init__(self):
        self.df = None
        
    @classmethod
    def parameters(cls):
        parser = ArgumentParser(description="Analyze scoring results across all cases with scores")
        parser.add_argument("--output-dir", type=Path, default=Path("analysis_outputs"), 
                          help="Directory to save plots and reports")
        parser.add_argument("--min-score-id", type=int, default=3994, 
                          help="Minimum score ID to include (default: 3994)")
        return parser.parse_args()
    
    def load_data(self, min_score_id: int = 3994) -> pd.DataFrame:
        """Load all scoring data from the database for cases with validated rubrics."""
        query = f"""
        SELECT s.id as score_id, s.rubric_id, s.generated_note_id, s.overall_score, 
               gn.case_id, gn.text_llm_vendor as note_vendor, gn.text_llm_name as note_model,
               s.created, s.text_llm_vendor as scoring_vendor, s.scoring_result,
               r.rubric as rubric_json, r.author as rubric_author
        FROM score s 
        JOIN generated_note gn ON s.generated_note_id = gn.id 
        JOIN rubric r ON s.rubric_id = r.id
        WHERE s.id >= {min_score_id}
        ORDER BY gn.case_id, s.created DESC
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
        """Generate a comprehensive text report with key statistics across all cases."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        report = []
        report.append(f"=== ALL CASES SCORING ANALYSIS ===\\n")
        
        # Basic stats
        total_scores = len(self.df)
        unique_notes = self.df['generated_note_id'].nunique()
        unique_rubrics = self.df['rubric_id'].nunique()
        unique_cases = self.df['case_id'].nunique()
        unique_authors = self.df['rubric_author'].nunique()
        
        report.append(f"Total Scores: {total_scores}")
        report.append(f"Unique Cases: {unique_cases}")
        report.append(f"Unique Notes: {unique_notes}")
        report.append(f"Unique Rubrics: {unique_rubrics}")
        report.append(f"Unique Authors: {unique_authors}")
        report.append("")
        
        # Case distribution
        case_counts = self.df['case_id'].value_counts().sort_index()
        report.append(f"Cases analyzed: {list(case_counts.index)}")
        report.append(f"Scores per case: min={case_counts.min()}, max={case_counts.max()}, mean={case_counts.mean():.1f}")
        report.append("")
        
        # Vendor comparison - Raw scores
        vendor_stats_raw = self.df.groupby('note_vendor_clean')['overall_score'].agg([
            'count', 'mean', 'std', 'min', 'max', 'median'
        ]).round(2)
        
        # Vendor comparison - Normalized scores (percentages)
        vendor_stats_norm = self.df.groupby('note_vendor_clean')['normalized_score'].agg([
            'mean', 'std', 'min', 'max', 'median'
        ]).round(2)
        
        report.append("=== VENDOR COMPARISON (Raw Scores) ===")
        report.append(vendor_stats_raw.to_string())
        report.append("")
        
        report.append("=== VENDOR COMPARISON (Normalized %) ===")
        report.append(vendor_stats_norm.to_string())
        report.append("")
        
        # Case-level performance
        case_vendor_stats = self.df.groupby(['case_id', 'note_vendor_clean'])['normalized_score'].agg([
            'count', 'mean', 'std'
        ]).round(2)
        
        report.append("=== CASE-LEVEL VENDOR PERFORMANCE (Normalized %) ===")
        report.append(case_vendor_stats.to_string())
        report.append("")
        
        # Rubric difficulty analysis
        rubric_stats = self.df.groupby(['rubric_id', 'rubric_author'])['normalized_score'].agg([
            'count', 'mean', 'std', 'min', 'max'
        ]).round(2)
        
        report.append("=== RUBRIC DIFFICULTY ANALYSIS (Normalized %) ===")
        report.append(rubric_stats.to_string())
        report.append("")
        
        # Author-level analysis
        author_stats = self.df.groupby('rubric_author')['normalized_score'].agg([
            'count', 'mean', 'std', 'min', 'max'
        ]).round(2)
        
        report.append("=== AUTHOR-LEVEL ANALYSIS (Normalized %) ===")
        report.append(author_stats.to_string())
        
        return "\\n".join(report)
    
    def create_vendor_boxplot(self, output_dir: Path) -> None:
        """Create overall vendor performance boxplot with outlier counts."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Color palettes
        vendor_colors = {'Anthropic': '#FF6B6B', 'Openai': '#4ECDC4'}
        
        sns.boxplot(data=self.df, x='note_vendor_clean', y='normalized_score', 
                   hue='note_vendor_clean', palette=vendor_colors, ax=ax, legend=False)
        ax.set_title('Overall Vendor Performance Distribution', fontsize=16, fontweight='bold')
        ax.set_xlabel('Vendor', fontsize=14)
        ax.set_ylabel('Normalized Score (%)', fontsize=14)
        ax.set_ylim(0, 100)
        
        # Calculate and add count annotations with outlier info
        for i, vendor in enumerate(self.df['note_vendor_clean'].unique()):
            vendor_data = self.df[self.df['note_vendor_clean'] == vendor]['normalized_score']
            count = len(vendor_data)
            
            # Calculate outliers using IQR method
            q1 = vendor_data.quantile(0.25)
            q3 = vendor_data.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            outliers = vendor_data[(vendor_data < lower_bound) | (vendor_data > upper_bound)]
            outlier_count = len(outliers)
            
            # Add annotations
            ax.text(i, 95, f'n={count}', ha='center', fontweight='bold', fontsize=12)
            ax.text(i, 90, f'{outlier_count} outliers', ha='center', fontsize=10, 
                   style='italic', color='darkred')
        
        plt.tight_layout()
        plt.savefig(output_dir / "vendor_performance_boxplot.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_case_comparison_scatter(self, output_dir: Path) -> None:
        """Create case-by-case vendor comparison scatter plot."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        case_vendor_means = self.df.groupby(['case_id', 'note_vendor_clean'])['normalized_score'].mean().unstack(fill_value=0)
        
        if 'Anthropic' in case_vendor_means.columns and 'Openai' in case_vendor_means.columns:
            ax.scatter(case_vendor_means['Openai'], case_vendor_means['Anthropic'], 
                       alpha=0.7, s=100, color='steelblue')
            ax.plot([0, 100], [0, 100], 'k--', alpha=0.5, label='Equal performance line')
            ax.set_xlabel('OpenAI Mean Score (%)', fontsize=14)
            ax.set_ylabel('Anthropic Mean Score (%)', fontsize=14)
            ax.set_title('Case-by-Case Vendor Comparison', fontsize=16, fontweight='bold')
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.legend(fontsize=12)
            ax.grid(True, alpha=0.3)
            
            # Add case labels
            for case_id in case_vendor_means.index:
                if case_vendor_means.loc[case_id, 'Openai'] > 0 and case_vendor_means.loc[case_id, 'Anthropic'] > 0:
                    ax.annotate(f'{case_id}', 
                               (case_vendor_means.loc[case_id, 'Openai'], 
                                case_vendor_means.loc[case_id, 'Anthropic']),
                               xytext=(3, 3), textcoords='offset points', fontsize=9, alpha=0.8)
        
        plt.tight_layout()
        plt.savefig(output_dir / "case_by_case_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_case_performance_bar(self, output_dir: Path) -> None:
        """Create mean performance by case bar chart with readable labels."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        fig, ax = plt.subplots(figsize=(20, 10))  # Extra wide for case labels
        
        case_means = self.df.groupby('case_id')['normalized_score'].mean().sort_values()
        
        # Create color gradient based on performance
        colors = plt.cm.RdYlGn([score/100 for score in case_means.values])
        
        bars = ax.bar(range(len(case_means)), case_means.values, alpha=0.8, color=colors)
        ax.set_title('Mean Performance by Case (Sorted by Performance)', fontsize=16, fontweight='bold')
        ax.set_xlabel('Case ID', fontsize=14)
        ax.set_ylabel('Mean Normalized Score (%)', fontsize=14)
        ax.set_ylim(0, 100)
        
        # Add case ID labels on x-axis with rotation
        ax.set_xticks(range(len(case_means)))
        ax.set_xticklabels(case_means.index, rotation=90, fontsize=10)
        
        # Add horizontal grid for easier reading
        ax.grid(True, axis='y', alpha=0.3)
        
        # Add value labels on top of bars for lowest and highest performers
        for i, (case_id, score) in enumerate(case_means.items()):
            if i < 5 or i >= len(case_means) - 5:  # Label first 5 and last 5
                ax.text(i, score + 1, f'{score:.1f}%', ha='center', fontsize=9, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(output_dir / "case_performance_ranking.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def create_score_distribution(self, output_dir: Path) -> None:
        """Create overlapping score distribution histogram."""
        if self.df is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Color palettes with transparency for overlap
        vendor_colors = {'Anthropic': '#FF6B6B', 'Openai': '#4ECDC4'}
        
        # Create overlapping histograms
        for vendor in self.df['note_vendor_clean'].unique():
            vendor_data = self.df[self.df['note_vendor_clean'] == vendor]['normalized_score']
            ax.hist(vendor_data, alpha=0.6, label=vendor, bins=30, 
                   color=vendor_colors.get(vendor, 'gray'), density=True)
        
        ax.set_title('Score Distribution by Vendor (Overlapping)', fontsize=16, fontweight='bold')
        ax.set_xlabel('Normalized Score (%)', fontsize=14)
        ax.set_ylabel('Density', fontsize=14)
        ax.set_xlim(0, 100)
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add mean lines
        for vendor in self.df['note_vendor_clean'].unique():
            vendor_data = self.df[self.df['note_vendor_clean'] == vendor]['normalized_score']
            mean_score = vendor_data.mean()
            ax.axvline(mean_score, color=vendor_colors.get(vendor, 'gray'), 
                      linestyle='--', linewidth=2, alpha=0.8,
                      label=f'{vendor} Mean: {mean_score:.1f}%')
        
        plt.tight_layout()
        plt.savefig(output_dir / "score_distribution_overlap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    def run_analysis(self, output_dir: Path, min_score_id: int = 3994) -> None:
        """Run complete analysis across all cases and save results."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Loading data for all cases with scores >= {min_score_id}...")
        self.load_data(min_score_id)
        
        unique_cases = sorted(self.df['case_id'].unique())
        print(f"Found {len(self.df)} scores across {len(unique_cases)} cases: {unique_cases}")
        
        print(f"Generating comprehensive report...")
        report = self.generate_report()
        
        # Save report
        report_path = output_dir / f"all_cases_analysis.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"Creating individual plots...")
        self.create_vendor_boxplot(output_dir)
        self.create_case_comparison_scatter(output_dir)
        self.create_case_performance_bar(output_dir)
        self.create_score_distribution(output_dir)
        
        # Save data for further analysis
        data_path = output_dir / f"all_cases_data.csv"
        self.df.to_csv(data_path, index=False)
        
        print(f"\\nAnalysis complete!")
        print(f"Report saved to: {report_path}")
        print(f"Plots saved to: {output_dir}")
        print(f"  - vendor_performance_boxplot.png")
        print(f"  - case_by_case_comparison.png")
        print(f"  - case_performance_ranking.png")
        print(f"  - score_distribution_overlap.png")
        print(f"Data saved to: {data_path}")
        print(f"\\n{report}")
    
    @classmethod
    def run(cls) -> None:
        args = cls.parameters()
        analyzer = cls()
        analyzer.run_analysis(args.output_dir, args.min_score_id)


if __name__ == "__main__":
    AllCasesScoreAnalyzer.run()